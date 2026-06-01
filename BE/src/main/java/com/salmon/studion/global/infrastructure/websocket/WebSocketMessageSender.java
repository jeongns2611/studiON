package com.salmon.studion.global.infrastructure.websocket;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.global.infrastructure.websocket.common.WsErrorResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class WebSocketMessageSender {

    private final ObjectMapper objectMapper;
    private final ProjectSessionManager sessionManager;

    public void broadcast(Integer projectId, String event, Object payload) throws IOException {
        String message = objectMapper.writeValueAsString(Map.of("event", event, "payload", payload));
        for (WebSocketSession s : sessionManager.getSessions(projectId)) {
            if (s.isOpen()) {
                s.sendMessage(new TextMessage(message));
            }
        }
    }

    public void sendToSession(WebSocketSession session, String event, Object payload) throws IOException {
        String message = objectMapper.writeValueAsString(Map.of("event", event, "payload", payload));
        if (session.isOpen()) {
            session.sendMessage(new TextMessage(message));
        }
    }

    public void sendError(WebSocketSession session, int code, String message) throws IOException {
        String payload = objectMapper.writeValueAsString(
                Map.of("event", "ERROR", "payload", new WsErrorResponse(code, message))
        );
        if (session.isOpen()) {
            session.sendMessage(new TextMessage(payload));
        }
    }
}
