import inspect
from pytorch_forecasting import TemporalFusionTransformer
print(inspect.signature(TemporalFusionTransformer.interpret_output))
print(inspect.getsource(TemporalFusionTransformer.interpret_output)[:18000])
