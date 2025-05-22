# API Documentation

API for searching Azure DevOps repositories and generating AI responses.

## Overview

This API provides an AI-powered search and chat interface for Azure DevOps repositories. The typical workflow is:

1. Use `/api/search` or `/api/search/scope` to retrieve relevant content
2. Feed the search results into `/api/chat` as user messages
3. Get AI-powered analysis using GPT-4.1 model

### Workflow Example

1. Search for content:
```json
POST /api/search
{
  "sources": [
    {
      "query": "account table schema",
      "repositories": ["AdsAppsMT"]
    }
  ]
}
```

2. Use search results in chat:
```json
POST /api/chat
{
  "messages": [
    {
      "role": "user",
      "content": "Here's the account table schema: [search results]. Please explain the relationships."
    }
  ]
}
```

The chat endpoint uses GPT-4.1 to analyze and explain the content found in the search step.

## Endpoints

### 1. Document Search

**POST** `/api/search`

Search documents with AI-powered analysis.

#### Request Body

```json
{
  "sources": [
    {
      "query": "search query",
      "repositories": ["repo1", "repo2"]
    }
  ],
  "stream_response": true,  // Default: true
  "custom_prompt": "optional custom prompt"  // Default: null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| sources | array | Required | List of search sources with query and repositories |
| sources[].query | string | Required | The search query to execute |
| sources[].repositories | array | Required | List of repository names to search in |
| stream_response | boolean | true | Whether to stream the response or return all at once |
| custom_prompt | string | null | Optional prompt to customize AI analysis |

#### Response

##### Streaming (stream_response=true)
Server-Sent Events (SSE) with:
- Initial prompt and context
- Streaming AI response chunks
- Completion status

##### Non-streaming
```json
{
  "status": "success|error",
  "codes": "search context",
  "content": "AI response",
  "error": "error message if any"
}
```

### 2. Scope Script Search

**POST** `/api/search/scope`

Search and analyze scope scripts.

#### Request Body

```json
{
  "repository": "AdsAppsMT",  // Default: "AdsAppsMT"
  "query": "image (ext:script)",     // Defailt: "(ext:script)"
  "branch": "master",         // Default: "master"
  "max_results": 1000,        // Default: 1000
  "stream_response": true,    // Default: true
  "custom_prompt": null       // Default: null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| repository | string | "AdsAppsMT" | The repository to search in |
| branch | string | "master" | The branch to search in |
| max_results | number | 1000 | Maximum number of results to return |
| stream_response | boolean | true | Whether to stream the response |
| custom_prompt | string | null | Optional prompt to customize analysis |

All fields are optional and will use the default values if not specified.

#### Response

##### Streaming (stream_response=true)
SSE events with:
- Scope knowledge base
- Code samples
- AI analysis chunks

##### Non-streaming
```json
{
  "status": "success|error",
  "scope_knowledge": "base knowledge",
  "codes": "code samples",
  "content": "AI analysis",
  "error": "error message if any"
}
```

### 3. Chat

**POST** `/api/chat`

Interactive chat with repository context and optional deep research.
messages are sent in a structured format. Exact allignment with the [OpenAI API](https://platform.openai.com/docs/api-reference/chat/create)

#### Request Body

```json
{
  "messages": [              // Required
    {
      "role": "user|assistant",  // Required: either "user" or "assistant" or "system"
      "content": "message text"  // Required: the message content
    }
  ],
  "stream_response": true    // Default: true
}
```

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| messages | array | - | Yes | Array of message objects |
| messages[].role | string | - | Yes | Either "user" or "assistant" or "system" |
| messages[].content | string | - | Yes | The message text |
| stream_response | boolean | true | No | Whether to stream the response |

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| repositories | string | "" | Comma-separated list of repositories |
| is_deep_research | boolean | false | Enable iterative deep research mode |
| temperature | float | 0.7 | Model temperature (0.0-2.0). Controls response creativity |

#### Response

##### Streaming
SSE events with:
- Chat response chunks
- Research progress (if deep_research=true)
- Completion status

##### Deep Research Mode Events
- Research iteration progress (max 5 iterations)
- Keyword expansion updates
- Consolidated findings

### 4. Note Management

#### List Notes
**GET** `/api/note`

```json
{
  "status": "success",
  "notes": []
}
```

#### Create Note
**POST** `/api/note`

Request:
```json
{
  "content": "Note content"
}
```

Response:
```json
{
  "status": "success",
  "id": "note_id",
  "title": "Generated note title"
}
```

#### Update Note
**PUT** `/api/note/{note_id}`

Request:
```json
{
  "content": "Updated content",
  "title": "Updated title"
}
```

#### Delete Note
**DELETE** `/api/note/{note_id}`

Response:
```json
{
  "status": "success",
  "message": "Note deleted"
}
```

## Error Handling

### HTTP Status Codes

| Code | Description | Examples |
|------|-------------|----------|
| 400 | Bad Request | No relevant content found, Search failure |
| 500 | Internal Server Error | Unexpected server exceptions |

### Error Response Format
```json
{
  "status": "error",
  "detail": "error message"
}
```

## Streaming Response Format

### SSE Event Structure
```json
{
  "event": "prompt|processing|message",
  "data": {
    "content": "message content",
    "message": "status message",
    "done": boolean
  }
}
```

### Event Types

| Event | Description |
|-------|-------------|
| prompt | Initial context and search results |
| processing | Progress updates |
| message | AI response chunks |
| systemprompt | (scope search only) Knowledge base |

## Special Features

### Deep Research Mode
- Iterative search process (up to 5 iterations)
- Progressive context expansion
- Keyword-based exploration
- Merged and deduplicated search results
- Step-by-step progress updates

### Custom Prompts
- Available in all endpoints
- Overrides default prompting behavior
- Affects AI response generation and analysis style
- Maintains base functionality while allowing customization