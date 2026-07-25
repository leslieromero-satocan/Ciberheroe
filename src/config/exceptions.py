class GraphQLError(Exception):
    pass

class QueryError(GraphQLError):
    def __init__(self, message, status_code=None) -> None:
        super().__init__(message)
        self.status_code = status_code

class APIRequestError(GraphQLError):
    def __init__(self, message, status_code=None) -> None:
        super().__init__(message)
        self.status_code = status_code