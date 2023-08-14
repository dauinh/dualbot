class AuthenticationError(Exception):
    """Exception raised when user is not signed in

    Attributes:
        message -- explanation of the error
    """
    def __init__(self):
        self.message = "User is not authenticated"
        super().__init__(self.message)


class SubscriptionError(Exception):
    """Exception raised when user has not picked a subscription package

    Attributes:
        message -- explanation of the error
    """
    def __init__(self):
        self.message = "No package selected"
        super().__init__(self.message)