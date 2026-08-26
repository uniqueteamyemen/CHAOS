import inspect
from pytorch_forecasting.models.base_model import BaseModel
print(inspect.signature(BaseModel.predict))
print(inspect.getsource(BaseModel.predict)[:16000])
