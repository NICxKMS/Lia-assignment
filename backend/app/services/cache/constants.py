"""Cache TTL and key prefix constants."""

# Cache TTL constants (in seconds)
TTL_CONVERSATION_CONTEXT = 3600  # 1 hour - frequently accessed during chat
TTL_USER_CONVERSATIONS = 300  # 5 minutes - list updates frequently
TTL_CONVERSATION_DETAIL = 600  # 10 minutes - detailed view less frequent
TTL_CONVERSATION_METADATA = 1800  # 30 minutes - basic info
TTL_AVAILABLE_MODELS = 86400  # 24 hours - static data
TTL_RATE_LIMIT = 60  # 1 minute
TTL_USER_DATA = 900  # 15 minutes - auth data
TTL_SENTIMENT_METHODS = 86400  # 24 hours - static data
TTL_MESSAGE = 3600  # 1 hour - individual messages
TTL_USER_MESSAGES = 120  # 2 minutes - short TTL for cumulative sentiment (low ttl as requested)

# Cache key prefixes - using Redis naming conventions
KEY_PREFIX_CONVERSATION = "conv"  # conv:{id}:context, conv:{id}:meta
KEY_PREFIX_USER = "user"  # user:{id}:data, user:{id}:email:{email}
KEY_PREFIX_RATE = "rate"  # rate:{type}:{id}
KEY_PREFIX_MODELS = "models"  # models:all
KEY_PREFIX_HISTORY = "history"  # history:{user_id} (sorted set)
KEY_PREFIX_DETAIL = "detail"  # detail:{conv_id}
KEY_PREFIX_SENTIMENT = "sentiment"  # sentiment:methods
KEY_PREFIX_MESSAGE = "msg"  # msg:{conv_id}:{msg_id}
KEY_PREFIX_EMAIL_INDEX = "email"  # email:{email} -> user_id (for login lookup)
KEY_PREFIX_USER_MESSAGES = "usrmsg"  # usrmsg:{conv_id} -> list of user message contents
