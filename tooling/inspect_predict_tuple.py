import inspect
from pytorch_forecasting.models.base._base_model import PredictTuple
print('type=',PredictTuple)
print('fields=',getattr(PredictTuple,'_fields',None))
print('bases=',PredictTuple.__mro__)
print('dir=',[x for x in dir(PredictTuple) if not x.startswith('_')])
