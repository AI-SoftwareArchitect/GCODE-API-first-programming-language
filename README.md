# GCODE-API-first-programming-language

Custom Language for Rapid API Development
This project showcases a simple API built using a custom-designed programming language specifically tailored for rapid API development. The language aims to simplify the process of defining routes, handling requests, and managing data within an API context.

🚀 Key Features of the Custom Language
Concise Route Definitions: Easily define API endpoints with clear HTTP methods (GET, POST).
Built-in Request Body Handling: Specify expected request body parameters and their types directly in the route definition.
Dynamic Variable Management: Declare and manipulate variables (e.g., list int users, int total_added).
Direct JSON Response Generation: Construct JSON responses using string concatenation for simplicity.
Basic Conditional Logic: Implement simple if/else statements for flow control.
List Manipulation: Add elements to lists and access them by index.
💡 How it Works (API Showcase Example)
The provided api showcase block demonstrates a basic API with several routes for managing a list of users.

API Code Example
api showcase {
    var list int users;
    var int total_added = 0;

    users.add(10);
    users.add(20);

    route "/add" POST REQ_BODY [int newuser, string name] {
        users.add(newuser);
        return "{\"success\": true, \"added\": " + users[users_len - 1] + ", \"total\": " + total_added + ", \"count\": " + users_len + "}";
    }

    route "/all" GET {
        return "{\"users\": [" + users[0] + "," + users[1] + "," + users[2] + "," + users[3] + "," + users[4] + "], \"count\": " + users_len + "}";
    }

    route "/count" GET {
        return "{\"count\": " + users_len + "}";
    }

    route "/news" GET {
        return "newssssssssssssssssssssssssssss!!";
    }

    route "/last" GET {
        return "{\"last\": " + users[users_len - 1] + "}";
    }

    route "/reset" POST {
        if (users_len > 2) {
            users_len = 2;
            total_added = 0;
            return "{\"reset\": true, \"count\": " + users_len + "}";
        } else {
            return "{\"reset\": false, \"count\": " + users_len + "}";
        }
    }
}
🛣️ API Endpoints
Here's a breakdown of the available API endpoints and their functionality:

POST /add

Request Body: {"newuser": <int>, "name": "<string>"}
Description: Adds a new integer user to the users list.
Response Example: {"success": true, "added": 30, "total": 0, "count": 3}
GET /all

Description: Returns all users currently in the list. Note: This example assumes a fixed size for demonstration, in a real scenario, you'd iterate the list.
Response Example: {"users": [10, 20, 30, 40, 50], "count": 5}
GET /count

Description: Returns the current number of users in the list.
Response Example: {"count": 3}
GET /news

Description: A simple test endpoint returning a static string.
Response Example: "newssssssssssssssssssssssssssss!!"
GET /last

Description: Returns the last user added to the list.
Response Example: {"last": 30}
POST /reset

Description: Resets the users list to its initial state (containing only the first two elements) if the list has more than two elements. Resets total_added to 0.
Response Example (Success): {"reset": true, "count": 2}
Response Example (Failure): {"reset": false, "count": 2}
