package com.salmon.studion.global.infrastructure.websocket;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.global.common.enums.ProjectWebSocketEventType;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class ProjectWebSocketBroadcaster {

    private final ObjectMapper objectMapper;
    private final ProjectSessionManager projectSessionManager;

    public void broadcastToProject(
            Integer projectId,
            ProjectWebSocketEventType eventType,
            Object payload
    ) throws IOException {
        String message = createMessage(eventType, payload);
        for (WebSocketSession session : projectSessionManager.getSessions(projectId)) {
            sendMessage(session, message);
        }
    }

    public void broadcastToProjectExceptSession(
            Integer projectId,
            String excludedSessionId,
            ProjectWebSocketEventType eventType,
            Object payload
    ) throws IOException {
        String message = createMessage(eventType, payload);
        for (WebSocketSession session : projectSessionManager.getSessions(projectId)) {
            if (session.getId().equals(excludedSessionId)) {
                continue;
            }
            sendMessage(session, message);
        }
    }

    private String createMessage(ProjectWebSocketEventType eventType, Object payload) throws IOException {
        return objectMapper.writeValueAsString(Map.of(
                "event", eventType.name(),
                "payload", payload
        ));
    }

    private void sendMessage(WebSocketSession session, String message) throws IOException {
        if (session.isOpen()) {
            session.sendMessage(new TextMessage(message));
        }
    }
}
