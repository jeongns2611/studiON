package com.salmon.studion.global.infrastructure.websocket.util;

import org.springframework.web.socket.WebSocketSession;

import java.net.URI;
import java.util.Map;

public final class WebSocketSessionUtils {

    public static final String PROJECT_ID_ATTRIBUTE = "projectId";
    public static final String USER_ID_ATTRIBUTE = "userId";

    private WebSocketSessionUtils() {
    }

    public static Integer extractProjectId(URI uri) {
        String path = uri.getPath();
        return Integer.parseInt(path.split("/")[3]);
    }

    public static Integer getProjectId(WebSocketSession session) {
        Object projectId = session.getAttributes().get(PROJECT_ID_ATTRIBUTE);
        if (projectId instanceof Integer value) {
            return value;
        }
        return extractProjectId(session.getUri());
    }

    public static Integer getUserId(WebSocketSession session) {
        Object userId = session.getAttributes().get(USER_ID_ATTRIBUTE);
        if (userId instanceof Integer value) {
            return value;
        }
        return null;
    }

    public static Integer getUserId(Map<String, Object> attributes) {
        Object userId = attributes.get(USER_ID_ATTRIBUTE);
        if (userId instanceof Integer value) {
            return value;
        }
        return null;
    }
}
