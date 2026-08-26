import inspect
import json
import pytorch_forecasting
from pytorch_forecasting import TimeSeriesDataSet, TemporalFusionTransformer
from pytorch_forecasting.data import NaNLabelEncoder
print(json.dumps({
 'pytorch_forecasting':getattr(pytorch_forecasting,'__version__','unknown'),
 'TimeSeriesDataSet_init':str(inspect.signature(TimeSeriesDataSet.__init__)),
 'TFT_from_dataset':str(inspect.signature(TemporalFusionTransformer.from_dataset)),
 'TFT_init':str(inspect.signature(TemporalFusionTransformer.__init__)),
 'NaNLabelEncoder':str(inspect.signature(NaNLabelEncoder)),
},indent=2))
