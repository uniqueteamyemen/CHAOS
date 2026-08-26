import inspect
from pytorch_forecasting.data.timeseries import TimeSeriesDataSet
from pytorch_forecasting.data import TorchNormalizer
print('transform_values:\n',inspect.getsource(TimeSeriesDataSet.transform_values))
print('preprocess snippet:\n',inspect.getsource(TimeSeriesDataSet._preprocess_data)[:12000])
print('identity methods:\n',inspect.getsource(TorchNormalizer.get_parameters))
