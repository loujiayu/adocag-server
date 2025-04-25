
async def event_stream_to_response(async_generator):
    """Convert an async generator to a response-compatible format."""
    response_data = ""
    async for data in async_generator:
        response_data += data
    return response_data
