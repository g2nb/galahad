class SessionList:
    """ Keeps a list of all currently registered Galaxy sessions """
    sessions = []

    def register(self, session):
        """
        Register a new GalaxyInstance session for the provided server, username and password. Return the session.
        :param session:
        :return:
        """

        # Validate that the server is not already registered
        index = self._get_index(session.gi.url)
        new_server = index == -1

        # Add the new session to the list
        if new_server:  self.sessions.append(session)

        # Otherwise, replace old session
        else: self.sessions[index] = session

        return session

    def get(self, server):
        """
        Returns a registered GalaxyInstance object with a matching server url or index
        Returns None if no matching result was found
        :param server:
        :return:
        """

        # Handle indexes
        if isinstance(server, int):
            if server >= len(self.sessions): return None
            else: return self.sessions[server]

        # Handle server URLs
        index = self._get_index(server)
        if index == -1: return None
        else: return self.sessions[index]

    def make(self, server):
        """
        Returns the registered session, if one exists. Otherwise, returns None
        :param server:
        :return:
        """
        session = self.get(server)
        if session: return session
        elif isinstance(server, int): raise RuntimeError('make() does not support session indexes')
        else: return None

    def clean(self):
        """
        Clear all sessions from the sessions list
        :return:
        """
        self.sessions = []

    def _get_index(self, server_url):
        """
        Returns a registered GalaxyInstance object with a matching server url
        Returns -1 if no matching result was found
        :param server_url:
        :return:
        """
        for i in range(len(self.sessions)):
            session = self.sessions[i]
            if session.gi.url.startswith(server_url): return i
        return -1


"""
Galaxy Sessions Singleton
"""
session = SessionList()
