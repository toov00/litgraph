API_BASE = "https://api.openalex.org"

FULL_SELECT = (
    "id,title,publication_year,authorships,cited_by_count,"
    "abstract_inverted_index,primary_location,ids,"
    "referenced_works,related_works"
)
STUB_SELECT = (
    "id,title,publication_year,authorships,cited_by_count,primary_location"
)

REQUEST_TIMEOUT = 20
POLITE_DELAY = 0.1
RATE_LIMIT_WAIT = 10
MAX_RETRIES = 3
ABSTRACT_LIMIT = 400
DISPLAY_WIDTH = 72

OA_ID_PREFIX = 'https://openalex.org/'
