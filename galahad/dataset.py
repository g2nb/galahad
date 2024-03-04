from threading import Timer
from bioblend import ConnectionError
from bioblend.galaxy.objects.wrappers import Dataset, HistoryDatasetAssociation
from nbtools import UIOutput, EventManager, ToolManager
from .sessions import session
from .utils import GALAXY_LOGO, server_name, session_color, galaxy_url


class GalaxyDatasetWidget(UIOutput):
    """A widget for representing a Galaxy Dataset"""
    dataset = None

    def __init__(self, dataset=None, **kwargs):
        """Initialize the job widget"""
        self.dataset = dataset
        self.set_color(kwargs)
        self.set_logo(kwargs)
        UIOutput.__init__(self, origin=self.dataset_origin(), **kwargs)
        self.poll(**kwargs)  # Query the Galaxy server and begin polling, if needed

        # Register the event handler for Galaxy login
        EventManager.instance().register("galaxy.login", self.login_callback)

    def dataset_origin(self):
        if self.initialized(): return server_name(galaxy_url(self.dataset.gi))
        else: return ''

    def set_color(self, kwargs={}):
        # If color is already set, keep that color
        if 'color' in kwargs: return

        # Otherwise, set the color based on the session
        if self.initialized(): kwargs['color'] = session_color(galaxy_url(self.dataset.gi))
        else: kwargs['color'] = session_color()

        return kwargs['color']

    @staticmethod
    def set_logo(kwargs={}):
        # If logo is already set, keep that logo
        if 'logo' in kwargs: return

        # Otherwise, set the logo
        kwargs['logo'] = GALAXY_LOGO
        return kwargs['logo']

    def poll(self, **kwargs):
        """Poll the Galaxy server for the dataset info and display it in the widget"""

        # If a Dataset ID is set, attempt to initialize from SessionList
        self.initialize(session.get(0))

        if self.initialized():
            # Add the job information to the widget
            self.name = self.dataset.name
            self.origin = server_name(galaxy_url(self.dataset.gi))
            self.status = self.status_text()
            self.description = self.submitted_text()
            self.files = self.files_list()

            # Register any data
            self.register_data(group=self.dataset.container.name)

            # Send notification if completed
            self.handle_notification()

            # Update the menu items
            self.extra_file_menu_items = {
                'Download to Workspace': {
                    'action': 'method',
                    'code': 'workspace_download',
                    'params': '{"file_name": "{{file_name}}"}'
                },
            }

            # Begin polling if pending or running
            self.poll_if_needed()
        else:
            # Display error message if no initialized Dataset object is provided
            if 'name' not in kwargs: self.name = 'Not Authenticated'
            if 'error' not in kwargs: self.error = 'You must authenticate before the dataset can be displayed. After you authenticate it may take a few seconds for the information to appear.'

    def poll_if_needed(self):
        """Begin a polling interval if the job is pending or running"""
        if not self.dataset.state == 'ok' and not self.dataset.state == 'error':
            timer = Timer(15.0, lambda: self.dataset.refresh() and self.poll())
            timer.start()

    def submitted_text(self):
        """Return pretty dataset submission text"""
        if not self.initialized(): return  # Ensure the job has been set
        return f"Created by {self.dataset.gi.gi.email} on {self.dataset.wrapped['create_time']}"

    def files_list(self):
        """Return the file URL is in the format the widget can handle"""
        if not self.initialized(): return  # Ensure the dataset has been set
        return [(f"{galaxy_url(self.dataset.gi)}{self.dataset.wrapped['download_url']}",
                 self.dataset.name, self.dataset.wrapped['extension'])]

    def handle_notification(self):
        if self.dataset.state == 'error':
            ToolManager.instance().send('notification', {'message': f'{self.name} has an error!', 'sender': 'Galaxy'})
        elif self.dataset.state == 'ok':
            ToolManager.instance().send('notification', {'message': f'{self.name} is ready!', 'sender': 'Galaxy'})

    def status_text(self):
        """Return human-friendly status text"""
        if not self.initialized():              return ''  # Ensure the Galaxy instance has been set
        else:                                   return self.dataset.state

    def workspace_download(self, file_name):
        with open(file_name, 'wb') as f:
            self.dataset.download(f)

    def initialize(self, session):
        """Retrieve the Dataset object from the session, return whether it is initialized"""
        if self.initialized(): return True
        if not self.dataset or not session: return False

        # Attempt to initialize the dataset
        try:
            self.dataset = session.datasets.get(self.dataset)
            self.error = ''
            self.set_color()
            return True
        except ConnectionError: return False

    def initialized(self):
        """Has the widget been initialized with session credentials"""
        return self.dataset and (isinstance(self.dataset, Dataset) or isinstance(self.dataset, HistoryDatasetAssociation))

    def login_callback(self, data):
        """Callback for after a user authenticates"""
        initialized = self.initialize(data)
        if initialized: self.poll()
        else: self.error = 'Error retrieving Galaxy dataset'
