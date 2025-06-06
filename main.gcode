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