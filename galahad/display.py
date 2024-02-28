import IPython

from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.objects.wrappers import Dataset, HistoryDatasetAssociation, Tool

from .dataset import GalaxyDatasetWidget
from .authentication import GalaxyAuthWidget
from .tool import GalaxyToolWidget


def display(content, **kwargs):
    """
    Display a widget, text or other media in a notebook without the need to import IPython at the top level.
    :param content:
    :return:
    """
    if isinstance(content, GalaxyInstance):
        IPython.display.display(GalaxyAuthWidget(content))
    elif isinstance(content, Tool):
        IPython.display.display(GalaxyToolWidget(content, **kwargs))
    elif isinstance(content, Dataset) or isinstance(content, HistoryDatasetAssociation):
        IPython.display.display(GalaxyDatasetWidget(content))
    else:
        IPython.display.display(content)