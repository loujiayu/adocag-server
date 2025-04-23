from azure.identity import AzureCliCredential, DefaultAzureCredential, AzurePowerShellCredential
import redis

# get an AAD access token scoped to Redis
# cred  = AzureCliCredential(subscription="ee52bcb5-ff93-4f02-8c74-148c217169bc")
# token = cred.get_token("https://adocag.redis.cache.windows.net/.default").token
key="PLCBg9MTuEZM52TJtv4r0iWeoizJ2oWxtAzCaJrtJKA="
r = redis.Redis(
    host="adocag.redis.cache.windows.net",
    port=6380,
    password=key,
    ssl=True
)

print(r.ping())   # True
