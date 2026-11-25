# Vendored R-FPOP implementation notice

The source files in this directory are from **robseg** by Guillem Rigaill, pinned to upstream commit
`ce49c26aa5b5eee84a835e69cbb7ca572f669792` (2019-07-02).

Upstream repository: https://github.com/guillemr/robust-fpop

Upstream package metadata declares `License: LGPL (>= 2.1)`. The original source files retain their copyright, attribution, warranty disclaimer and LGPL notices. The full LGPL-2.1 license text is supplied in `COPYING.LGPL-2.1`.

The added `chaos_robseg_wrapper.cpp` is a small C ABI wrapper authored for CHAOS; it invokes the upstream R-FPOP routine with a symmetric Huber loss. It does not change the upstream segmentation algorithm.

CHAOS uses this implementation only in the separately reported retrospective segmentation track. It is not counted as an online detector or ranked by online detection delay.
