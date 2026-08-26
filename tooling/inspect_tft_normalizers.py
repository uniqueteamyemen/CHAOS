import inspect
import json
from pytorch_forecasting.data import TorchNormalizer, EncoderNormalizer
print(json.dumps({'TorchNormalizer':str(inspect.signature(TorchNormalizer)),'EncoderNormalizer':str(inspect.signature(EncoderNormalizer)),'TorchNormalizer_doc':TorchNormalizer.__doc__[:1200]},indent=2))
