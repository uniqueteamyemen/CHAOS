const express = require('express');
const crypto = require('crypto');
const Redis = require('ioredis');

const app = express();
app.use(express.json());

// ========== 1. المتانة: التحقق من سر المنصة ==========
const PLATFORM_SECRET = process.env.PLATFORM_SECRET;
if (!PLATFORM_SECRET) {
  console.error('FATAL: PLATFORM_SECRET environment variable is required.');
  process.exit(1);
}
const API_KEY = process.env.API_KEY;
if (!API_KEY) {
  console.error('FATAL: API_KEY environment variable is required.');
  process.exit(1);
}

// ========== 2. إعداد Redis مع وضع الطوارئ التلقائي (Automatic Memory Fallback) ==========
let redis;
let usingMemoryFallback = false;

if (!process.env.REDIS_URL) {
  console.log('⚠️  Redis not found. Running in ephemeral in-memory demo mode.');
  usingMemoryFallback = true;
  redis = {
    data: new Map(),
    bootId: crypto.randomBytes(16).toString('hex'),
    async get(key) { return this.data.get(key); },
    async set(key, value, ...args) {
      const hasNX = args.includes('NX');
      if (hasNX && this.data.has(key)) return null;
      this.data.set(key, value);
      return 'OK';
    },
    async del(key) { this.data.delete(key); return 1; },
    async ping() { return 'PONG'; },
    async incr(key) {
      const current = Number(this.data.get(key) || 0);
      const next = current + 1;
      this.data.set(key, next);
      return next;
    },
    // دالة مخصصة لدعم سجل التدقيق (appendLog)
    async rpush(key, value) {
      if (!this.data.has(key)) this.data.set(key, []);
      this.data.get(key).push(value);
      return this.data.get(key).length;
    }
  };
} else {
  redis = new Redis(process.env.REDIS_URL);
  console.log('✅ Connected to Redis');
}

// ========== 3. التدقيق: سجل إضافي (Append-only Log) ==========
async function appendLog(event) {
  const entry = JSON.stringify({ ...event, ts: Date.now() });
  await redis.rpush('audit_log', entry);
}

// ========== 3b. الذرية: قفل جلسة واحد للتعديل المتزامن ==========
// كل معالجة تقرأ الجلسة ثم تكتبها. بدون قفل، طلبان متزامنان يقرآن النسخة نفسها
// فيكتب أحدهما فوق إشارة الآخر. القفل يجعل «اقرأ-عدّل-اكتب» عملية واحدة لكل جلسة.
async function acquireLock(h0, ttlSeconds = 15, waitMs = 10000) {
  const token = crypto.randomBytes(12).toString('hex');
  const deadline = Date.now() + waitMs;
  while (Date.now() < deadline) {
    const ok = await redis.set(`lock:${h0}`, token, 'NX', 'EX', ttlSeconds);
    if (ok) return token;
    await new Promise(r => setTimeout(r, 20));
  }
  return null;
}

async function releaseLock(h0, token) {
  const current = await redis.get(`lock:${h0}`);
  if (current === token) await redis.del(`lock:${h0}`);
}

// حجز ذري لإشارة الفتح: أمر واحد، بلا قفل وبلا طابور.
// يمنع التكرار فورًا، ويترك القفل للكتابة على الجلسة فقط.
async function claimUnlock(req, res, next) {
  const h0 = req.body && req.body.h0;
  if (!h0) return next();
  const claimed = await redis.set(`unlock:${h0}`, '1', 'NX', 'EX', 3600);
  if (!claimed) {
    return res.status(409).json({ error: 'user_unlock already recorded' });
  }
  next();
}

async function lockSession(req, res, next) {
  const h0 = req.body && req.body.h0;
  if (!h0) return next();
  const token = await acquireLock(h0);
  if (!token) {
    return res.status(503).json({ error: 'Session busy, retry' });
  }
  let released = false;
  const release = async () => { if (!released) { released = true; await releaseLock(h0, token); } };
  res.on('finish', release);
  res.on('close', release);
  next();
}

// ========== 4. المتانة: منع تكرار الطلبات (Idempotency Middleware) ==========
async function idempotency(req, res, next) {
  const key = req.headers['idempotency-key'];
  if (!key) return next();
  const bodyHash = crypto.createHash('sha256').update(JSON.stringify(req.body || {})).digest('hex');
  const cacheKey = `idempotent:${key}:${req.path}:${bodyHash}`;

  const cached = await redis.get(cacheKey);
  if (cached) {
    const parsed = JSON.parse(cached);
    if (
      parsed &&
      typeof parsed === 'object' &&
      Object.prototype.hasOwnProperty.call(parsed, 'status') &&
      Object.prototype.hasOwnProperty.call(parsed, 'body')
    ) {
      return res.status(parsed.status).json(parsed.body);
    }
    return res.json(parsed);
  }

  const originalSend = res.json.bind(res);
  res.json = async (body) => {
    await redis.set(
      cacheKey,
      JSON.stringify({
        status: res.statusCode,
        body
      }),
      'EX',
      300
    );
    return originalSend(body);
  };
  next();
}
app.use(idempotency);

function requireApiKey(req, res, next) {
  if (req.path === '/v1/health') return next();
  const key = req.headers['x-api-key'];
  if (key !== API_KEY) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
}
app.use(requireApiKey);

// ========== 5. المتانة: دالة مساعدة للتحقق من صحة المدخلات ==========
function requireFields(obj, fields) {
  for (const f of fields) {
    if (obj[f] === undefined || obj[f] === null) return false;
  }
  return true;
}

function isSessionClosed(session) {
  return session && (session.status === 'CANCELLED' || session.status === 'CLOSED');
}

// ========== نقطة النهاية 1: فحص الصحة ==========
app.get('/v1/health', async (req, res) => {
  try {
    await redis.ping();
    res.json({ status: 'ok', redis: !usingMemoryFallback, service: 'paylock-core' });
  } catch (e) {
    res.status(500).json({ status: 'error', redis: false });
  }
});

// ========== Optional Webhooks (Provider-Enabled) ==========
// If a provider chooses to send payment receipts/cancellations to PayLock, the session can be closed automatically.
app.post('/v1/webhook/payment', lockSession, async (req, res) => {
  if (!requireFields(req.body, ['h0', 'receipt_id'])) {
    return res.status(400).json({ error: 'Missing required fields: h0, receipt_id' });
  }

  const { h0, receipt_id } = req.body;
  const sessionData = await redis.get(`session:${h0}`);
  if (!sessionData) return res.status(404).json({ error: 'Session not found' });

  const session = JSON.parse(sessionData);
  if (session.receipt_id && session.receipt_id !== receipt_id) {
    return res.status(409).json({
      error: 'Commercial receipt mismatch with frozen intent.'
    });
  }
  if (isSessionClosed(session)) {
    return res.status(409).json({ error: 'Session is closed' });
  }

  session.payment_receipt_id = receipt_id;
  session.payment_attested_at = Date.now();
  session.signals.push({ type: 'payment_attested', ref: receipt_id, timestamp: Date.now() });
  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
  await appendLog({ type: 'PAYMENT_ATTESTED', h0, receipt_id });

  res.json({ ok: true, h0 });
});

app.post('/v1/webhook/cancel', lockSession, async (req, res) => {
  if (!requireFields(req.body, ['h0', 'receipt_id'])) {
    return res.status(400).json({ error: 'Missing required fields: h0, receipt_id' });
  }

  const { h0, receipt_id, reason } = req.body;
  const sessionData = await redis.get(`session:${h0}`);
  if (!sessionData) return res.status(404).json({ error: 'Session not found' });

  const session = JSON.parse(sessionData);
  if (session.receipt_id && session.receipt_id !== receipt_id) {
    return res.status(409).json({
      error: 'Commercial receipt mismatch with frozen intent.'
    });
  }
  if (isSessionClosed(session)) {
    return res.json({ ok: true, h0, status: session.status });
  }

  session.status = 'CANCELLED';
  session.cancelled_at = Date.now();
  session.cancel_receipt_id = receipt_id;
  session.cancel_reason = reason || null;
  session.signals.push({ type: 'payment_cancelled', ref: receipt_id, timestamp: Date.now(), reason: reason || null });
  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
  await appendLog({ type: 'PAYMENT_CANCELLED', h0, receipt_id, reason: reason || null });

  res.json({ ok: true, h0, status: 'CANCELLED' });
});

// ========== نقطة النهاية 2: إنشاء جلسة (H0) ==========
app.post('/v1/session', async (req, res) => {
  if (!requireFields(req.body, ['service_id', 'device_id'])) {
    return res.status(400).json({ error: 'Missing required fields: service_id, device_id' });
  }

  const {
    service_id, service_name, provider_id, provider_name,
    device_id, device_type, device_specs,
    payment_method, service_url, constraints, receipt_id
  } = req.body;

  // Commercial uniqueness: prevent replaying the same commercial transaction.
  // Note: this does NOT prevent repeat purchases/consumption for the same service_id.
  if (receipt_id) {
    const receiptKey = `receipt:${receipt_id}`;
    const claimed = await redis.set(receiptKey, '1', 'NX', 'EX', 3600);
    if (!claimed) {
      return res.status(409).json({ error: 'Duplicate receipt_id' });
    }
  }

  const payload = {
    service_id, service_name: service_name || null,
    provider_id: provider_id || null, provider_name: provider_name || null,
    device_id, device_type: device_type || null, device_specs: device_specs || null,
    payment_method: payment_method || null, service_url: service_url || null,
    constraints: constraints || {}
  };

  const payloadString = JSON.stringify(payload);

  // H0 must be system-issued and non-reproducible from client-supplied data alone.
  // We inject a hidden per-session serial to prevent pre-computation and technical replay.
  const sessionSerial = await redis.incr('session_counter');
  const bootId = usingMemoryFallback ? redis.bootId : 'redis';
  const h0 = crypto.createHmac('sha256', PLATFORM_SECRET).update(`${payloadString}:${bootId}:${sessionSerial}`).digest('hex');

  const session = {
    h0, status: 'INITIATED', payload, device_id,
    receipt_id: receipt_id || null, created_at: Date.now(), signals: [], session_serial: sessionSerial
  };

  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
  await appendLog({ type: 'SESSION_CREATED', h0, service_id, device_id });

  res.json({ h0, status: 'INITIATED' });
});

// ========== نقطة النهاية 3: إلحاق إشارة ==========
app.post('/v1/signal', lockSession, async (req, res) => {
  if (!requireFields(req.body, ['h0', 'signal_type', 'signal_ref'])) {
    return res.status(400).json({ error: 'Missing required fields: h0, signal_type, signal_ref' });
  }

  const { h0, signal_type, signal_ref } = req.body;
  const sessionData = await redis.get(`session:${h0}`);
  if (!sessionData) return res.status(404).json({ error: 'Session not found' });

  const session = JSON.parse(sessionData);
  const isDuplicate = session.signals.some(
    s =>
      s.type === signal_type &&
      s.ref === signal_ref
  );

  if (isDuplicate) {
    return res.json({
      h0,
      signal_recorded: true,
      duplicate_ignored: true
    });
  }
  session.signals.push({ type: signal_type, ref: signal_ref, timestamp: Date.now() });
  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);

  await appendLog({ type: 'SIGNAL_RECORDED', h0, signal_type });

  res.json({ h0, signal_recorded: true });
});

// ========== نقطة النهاية 4: فتح القفل (Unlock) ==========
app.post('/v1/unlock', claimUnlock, lockSession, async (req, res) => {
  if (!requireFields(req.body, ['h0'])) {
    return res.status(400).json({ error: 'Missing required field: h0' });
  }

  const { h0, device_fingerprint } = req.body;
  const sessionData = await redis.get(`session:${h0}`);
  if (!sessionData) return res.status(404).json({ error: 'Session not found' });

  const session = JSON.parse(sessionData);
  if (isSessionClosed(session)) {
    return res.status(409).json({ error: 'Session is closed', status: session.status });
  }
  const unlockExists = session.signals.find(s => s.type === 'user_unlock');
  if (unlockExists) {
    return res.status(409).json({ error: 'user_unlock already recorded' });
  }

  session.signals.push({
    type: 'user_unlock',
    ref: device_fingerprint || 'not_provided',
    device_fingerprint: device_fingerprint || null,
    timestamp: Date.now()
  });

  await appendLog({ type: 'USER_UNLOCK_RECORDED', h0, device_fingerprint: device_fingerprint || null });

  // Opportunistic proof issuance: if provider_ack already exists, issue H1 immediately.
  const providerAck = session.signals.find(s => s.type === 'provider_ack');
  if (providerAck) {
    const h1Key = `h1:${h0}`;
    const existingH1 = await redis.get(h1Key);
    if (existingH1) {
      session.h1 = existingH1;
      session.status = 'EXECUTION_PROVEN';
      await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
      return res.json({ h0, status: 'UNLOCKED', h1: existingH1, proof_status: 'EXECUTION_PROVEN' });
    }

    const h1Payload = `${h0}:${providerAck.ref}:${session.device_id}`;
    const h1 = crypto.createHmac('sha256', PLATFORM_SECRET).update(h1Payload).digest('hex');
    const claimed = await redis.set(h1Key, h1, 'NX', 'EX', 3600);
    const winner = claimed ? h1 : await redis.get(h1Key);

    session.h1 = winner;
    session.status = 'EXECUTION_PROVEN';
    await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
    await appendLog({ type: 'RESOLVED', h0, h1: winner });

    return res.json({ h0, status: 'UNLOCKED', h1: winner, proof_status: 'EXECUTION_PROVEN' });
  }

  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);
  res.json({ h0, status: 'UNLOCKED' });
});

// ========== نقطة النهاية 4: الحل وإصدار H1 ==========
app.post('/v1/resolve', lockSession, async (req, res) => {
  if (!requireFields(req.body, ['h0'])) {
    return res.status(400).json({ error: 'Missing required field: h0' });
  }

  const { h0 } = req.body;
  const sessionData = await redis.get(`session:${h0}`);
  if (!sessionData) return res.status(404).json({ error: 'Session not found' });

  const session = JSON.parse(sessionData);
  if (isSessionClosed(session)) {
    return res.status(409).json({ error: 'Session is closed', status: session.status });
  }
  const h1Key = `h1:${h0}`;
  const existingH1 = await redis.get(h1Key);
  if (existingH1) return res.json({ h1: existingH1, status: 'EXECUTION_PROVEN' });

  const providerAck = session.signals.find(s => s.type === 'provider_ack');
  const userUnlock = session.signals.find(s => s.type === 'user_unlock');
  if (!providerAck || !userUnlock) {
    return res.status(400).json({
      error: 'Missing required signals',
      missing: {
        provider_ack: !providerAck,
        user_unlock: !userUnlock
      }
    });
  }

  const h1Payload = `${h0}:${providerAck.ref}:${session.device_id}`;
  const h1 = crypto.createHmac('sha256', PLATFORM_SECRET).update(h1Payload).digest('hex');
  const claimed = await redis.set(h1Key, h1, 'NX', 'EX', 3600);
  if (!claimed) {
    const winner = await redis.get(h1Key);
    return res.json({ h1: winner, status: 'EXECUTION_PROVEN' });
  }

  session.h1 = h1;
  session.status = 'EXECUTION_PROVEN';
  await redis.set(`session:${h0}`, JSON.stringify(session), 'EX', 3600);

  await appendLog({ type: 'RESOLVED', h0, h1 });

  res.json({ h1, status: 'EXECUTION_PROVEN' });
});

// ========== بدء الخادم ==========
const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  const mode = usingMemoryFallback
    ? 'Ephemeral Evaluation Mode (RAM-only)'
    : 'Durable Production Mode (Redis)';

  console.log(
    `PayLock Core [${mode}] running on port ${PORT}`
  );
});
