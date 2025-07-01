# QuizRealm Backend API Documentation

This document details all implemented API endpoints for the QuizRealm backend, accurately reflecting the FastAPI routes as found in `src/api/main.py`. It describes REST and WebSocket endpoints for authentication, quiz room management, question answering, leaderboards, user dashboards, health checks, and real-time updates.

---

## Authentication

### Signup

- **POST** `/signup`
- **Description**: Register a new user account.
- **Request Body** (`application/json`):
  ```json
  {
    "username": "string",
    "email": "user@example.com",
    "password": "min. 5 chars"
  }
  ```
- **Responses**:
  - `200 OK`: Returns the created user.
    ```json
    {
      "id": "user-uuid",
      "username": "string",
      "email": "user@example.com",
      "created_at": "timestamp"
    }
    ```
  - `400 Bad Request`: Username or email already taken.

---

### Login

- **POST** `/login`
- **Description**: Authenticate and receive a JWT access token.
- **Form Data** (`application/x-www-form-urlencoded` required by OAuth2PasswordRequestForm):
  - `username`: string
  - `password`: string
- **Responses**:
  - `200 OK`:
    ```json
    {
      "access_token": "jwt-string",
      "token_type": "bearer"
    }
    ```
  - `401 Unauthorized`: Invalid credentials.

---

## Rooms

All endpoints (except `/signup` and `/login`) **require JWT authentication** via the `Authorization: Bearer <token>` header.

### List All Rooms

- **GET** `/rooms`
- **Description**: List all active quiz rooms.
- **Response Example**:
  ```json
  [
    {
      "id": "room-uuid",
      "name": "Chess Quiz",
      "host_user_id": "user-uuid",
      "status": "waiting",
      "created_at": "timestamp"
    }
  ]
  ```

---

### Create Room

- **POST** `/rooms/create`
- **Description**: Create a new quiz room.
- **Request Body**:
  ```json
  {
    "name": "string",
    "host_user_id": "user-uuid"
  }
  ```
- **Response Example**:
  ```json
  {
    "id": "room-uuid",
    "name": "string",
    "host_user_id": "user-uuid",
    "status": "waiting",
    "created_at": "timestamp"
  }
  ```

---

### Join Room

- **POST** `/rooms/join`
- **Description**: Join an existing quiz room (stub, no participant tracking yet).
- **Request Body**:
  ```json
  {
    "room_id": "room-uuid"
  }
  ```
- **Response Example**:
  ```json
  {
    "message": "Joined <room name>",
    "room_id": "room-uuid"
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Room not found.

---

## Questions

### Get Questions for Room

- **GET** `/questions/{room_id}`
- **Description**: Retrieve all questions for a given room.
- **Path Parameters**:
  - `room_id`: string (room UUID)
- **Response Example**:
  ```json
  [
    {
      "id": "question-uuid",
      "room_id": "room-uuid",
      "text": "What is 2+2?",
      "options": ["1", "2", "3", "4"]
    }
  ]
  ```
> `correct_answer` is never sent to client.

---

## Responses & Answer Submission

### Submit an Answer

- **POST** `/responses`
- **Description**: Submit an answer to a quiz question. Updates and returns correctness, updates the user's score for the room.
- **Request Body**:
  ```json
  {
    "room_id": "room-uuid",
    "question_id": "question-uuid",
    "selected_option": "string"
  }
  ```
- **Response Example**:
  ```json
  {
    "id": "response-uuid",
    "user_id": "user-uuid",
    "room_id": "room-uuid",
    "question_id": "question-uuid",
    "selected_option": "string",
    "is_correct": true,
    "answered_at": "timestamp"
  }
  ```
- **Error Responses**:
  - `404 Not Found`: Question not found.

---

## Leaderboard & Dashboard

### Room Leaderboard

- **GET** `/leaderboard/{room_id}`
- **Description**: Shows the leaderboard (user scores) for a specific room.
- **Path Parameters**:
  - `room_id`: string
- **Response Example**:
  ```json
  [
    {
      "user_id": "user-uuid",
      "username": "playername",
      "total_score": 3
    }
  ]
  ```

---

### User Dashboard (Match History)

- **GET** `/dashboard`
- **Description**: Returns the authenticated user's recent quiz matches (past 50), including room name and final score.
- **Response Example**:
  ```json
  [
    {
      "room_id": "room-uuid",
      "final_score": 4,
      "finished_at": "timestamp",
      "room_name": "Chess Quiz"
    }
  ]
  ```

---

## Health Check

### Quiz Backend Health Check

- **GET** `/quiz-check`
- **Description**: Returns `{ "status": "OK" }` if backend is healthy.

---

### API Root Health Check

- **GET** `/`
- **Description**: API liveness probe. Returns `{ "message": "Healthy" }`

---

## Real-Time Updates: WebSocket Endpoints

These endpoints enable clients to participate in real-time quiz and leaderboard updates.

### Quiz Room WebSocket

- **WS** `/ws/room/{room_id}`
- **Description**: Connect to real-time quiz room events. Messages currently echo; no broadcast logic yet.
- **Path Parameter**: `room_id` (string)
- **Typical Use**: Connect with a real-time library, send/receive JSON messages.

### Leaderboard WebSocket

- **WS** `/ws/leaderboard/{room_id}`
- **Description**: Real-time updates for leaderboard events.
- **Path Parameter**: `room_id` (string)
- **Typical Use**: Connect, send, and receive leaderboard event messages.

### WebSocket Usage Help Endpoint

- **GET** `/realtime-help`
- **Description**: Sample usage metadata for frontend discovery/documentation. Returns:
  ```json
  {
    "websockets": [
      {
        "endpoint": "/ws/room/{room_id}",
        "purpose": "Quiz room real-time events",
        "usage": "Connect and receive/send messages"
      },
      {
        "endpoint": "/ws/leaderboard/{room_id}",
        "purpose": "Real-time leaderboard updates",
        "usage": "Connect and receive/send leaderboard messages"
      }
    ]
  }
  ```

---

## Authentication

All endpoints except `/signup`, `/login`, `/`, and `/quiz-check` **require JWT bearer tokens** in the header:

```
Authorization: Bearer <token>
```
Tokens are returned by `/login`.

---

## Summary Table

| Method | Path                         | Description                        | Auth Required |
|--------|------------------------------|------------------------------------|--------------|
| POST   | /signup                      | Register new user                  | No           |
| POST   | /login                       | Login (token)                      | No           |
| GET    | /rooms                       | List rooms                         | Yes          |
| POST   | /rooms/create                | Create room                        | Yes          |
| POST   | /rooms/join                  | Join room                          | Yes          |
| GET    | /questions/{room_id}         | Get questions for room             | Yes          |
| POST   | /responses                   | Submit answer to quiz question     | Yes          |
| GET    | /leaderboard/{room_id}       | Get room leaderboard               | Yes          |
| GET    | /dashboard                   | Get user match history             | Yes          |
| GET    | /quiz-check                  | Health check                       | No           |
| GET    | /                            | Root health check                  | No           |
| WS     | /ws/room/{room_id}           | Real-time room events              | Yes (token query param or header) |
| WS     | /ws/leaderboard/{room_id}    | Real-time leaderboard events       | Yes (token query param or header) |
| GET    | /realtime-help               | WebSocket help                     | No           |

---

## Data Models

This API uses the following models in requests and responses (see full details in source).

- **UserIn**: username, email, password
- **UserOut**: id, username, email, created_at
- **Token**: access_token, token_type
- **RoomCreate**: name, host_user_id
- **RoomOut**: id, name, host_user_id, status, created_at
- **RoomJoin**: room_id
- **QuestionOut**: id, room_id, text, options
- **ResponseIn**: room_id, question_id, selected_option
- **ResponseOut**: id, user_id, room_id, question_id, selected_option, is_correct, answered_at
- **ScoreOut**: user_id, username, total_score
- **MatchHistoryOut**: room_id, final_score, finished_at, room_name

> For further details on field types and constraints, see the Pydantic models in the backend code.

---

## Notes

- All cross-room, user, and leaderboard actions are processed server-side using SQLite.
- WebSocket endpoints are currently stubbed (no full broadcast yet).
- Correct answers are not exposed to the client in any API response.

