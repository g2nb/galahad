from bioblend.galaxy.objects import History
from nbtools import UIOutput, EventManager
from .sessions import session
from .utils import session_color, GALAXY_LOGO, server_name, galaxy_url


class GalaxyHistoryWidget(UIOutput):
    """A widget for representing a Galaxy History as a widget"""
    history = None

    def __init__(self, history=None, **kwargs):
        """Initialize the job widget"""
        self.history = history
        self.set_color(kwargs)
        self.set_logo(kwargs)
        UIOutput.__init__(self, origin=self.history_origin(), **kwargs)
        self.poll()  # Query the Galaxy server and begin polling, if needed

        # Register the event handler for Galaxy login
        EventManager.instance().register("galaxy.login", self.login_callback)

    def set_color(self, kwargs={}):
        # If color is already set, keep that color
        if 'color' in kwargs: return

        # Otherwise, set the color based on the session
        if self.initialized(): kwargs['color'] = session_color(galaxy_url(self.history.gi))
        else: kwargs['color'] = session_color()

        return kwargs['color']

    @staticmethod
    def set_logo(kwargs={}):
        # If logo is already set, keep that logo
        if 'logo' in kwargs: return

        # Otherwise, set the logo
        kwargs['logo'] = GALAXY_LOGO
        return kwargs['logo']

    def poll(self):
        """Poll the Galaxy server for the history info and display it in the widget"""

        # If a History ID is set, attempt to initialize from SessionList
        self.initialize(session.get(0))

        if self.initialized():
            # Add the job information to the widget
            self.name = self.history.name
            self.origin = server_name(galaxy_url(self.history.gi))
            self.description = self.history.wrapped['annotation'] if 'annotation' in self.history.wrapped and self.history.wrapped['annotation'] else ''
            self.files = self.files_list()

            # Begin polling if pending or running
            # self.poll_if_needed()
        else:
            # Display error message if no initialized History object is provided
            self.name = 'Not Authenticated'
            self.error = 'You must authenticate before the history can be displayed. After you authenticate it may take a few seconds for the information to appear.'

    def files_list(self):
        """Return the file URL is in the format the widget can handle"""
        if not self.initialized(): return  # Ensure the history has been set
        return [f"{galaxy_url(self.history.gi)}{dataset.wrapped['url']}/display" for dataset in self.history.content_infos]

    def history_origin(self):
        if self.initialized(): return server_name(galaxy_url(self.history.gi))
        else: return ''

    def initialize(self, session):
        """Retrieve the History object from the session, return whether it is initialized"""
        if self.initialized(): return True
        if not self.history or not session: return False

        # Attempt to initialize the dataset
        try:
            self.history = session.histories.get(self.history)
            self.error = ''
            self.set_color()
            return True
        except ConnectionError: return False

    def initialized(self):
        """Has the widget been initialized with session credentials"""
        return self.history and isinstance(self.history, History)

    def login_callback(self, data):
        """Callback for after a user authenticates"""
        initialized = self.initialize(data)
        if initialized: self.poll()
        else: self.error = 'Error retrieving Galaxy history'
