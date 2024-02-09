import IPython

from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.objects.wrappers import Dataset, HistoryDatasetAssociation, Tool

from .datasetwidget import GalaxyDatasetWidget
from .authwidget import GalaxyAuthWidget
from .toolwidget import GalaxyToolWidget


def display(content, **kwargs):
    """
    Display a widget, text or other media in a notebook without the need to import IPython at the top level.
    Also handles wrapping GenePattern Python Library content in widgets.
    :param content:
    :return:
    """
    if isinstance(content, GalaxyInstance):
        IPython.display.display(GalaxyAuthWidget(content))
    elif isinstance(content, Tool):
        # TODO: Cut spec handling?
        # if 'spec' in kwargs and isinstance(kwargs['spec'], gp.GPJobSpec): spec_to_kwargs(kwargs)
        IPython.display.display(GalaxyToolWidget(content, **kwargs))
    elif isinstance(content, Dataset) or isinstance(content, HistoryDatasetAssociation):
        IPython.display.display(GalaxyDatasetWidget(content))
    else:
        IPython.display.display(content)