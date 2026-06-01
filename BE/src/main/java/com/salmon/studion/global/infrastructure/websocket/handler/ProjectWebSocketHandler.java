package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.project.service.ProjectPresenceService;
import com.salmon.studion.global.common.enums.CommentWebSocketEventType;
import com.salmon.studion.global.common.enums.ProjectWebSocketEventType;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.websocket.ProjectSessionManager;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
import com.salmon.studion.global.infrastructure.websocket.util.WebSocketSessionUtils;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class ProjectWebSocketHandler extends TextWebSocketHandler {

    private final ProjectSessionManager sessionManager;
    private final ProjectPresenceService projectPresenceService;
    private final ObjectMapper objectMapper;
    private final ProjectEventHandler projectEventHandler;
    private final CommentEventHandler commentEventHandler;
    private final TrackEventHandler trackEventHandler;
    private final ClipEventHandler clipEventHandler;
    private final EqEventHandler eqEventHandler;
    private final WebSocketMessageSender webSocketMessageSender;

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        Integer projectId = WebSocketSessionUtils.getProjectId(session);
        sessionManager.register(projectId, session);
        log.info("[WS 연결 성공]: session_id={}, project_id={}", session.getId(), projectId);
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) throws IOException {
        WsMessage<Map> raw = objectMapper.readValue(
                message.getPayload(),
                objectMapper.getTypeFactory().constructParametricType(WsMessage.class, Map.class)
        );

        String event = raw.getEvent();
        Integer projectId = WebSocketSessionUtils.getProjectId(session);
        Integer userId = WebSocketSessionUtils.getUserId(session);

        try {
            bindSecurityContext(userId);

            ProjectWebSocketEventType projectEventType = ProjectWebSocketEventType.from(event);
            CommentWebSocketEventType commentEventType = CommentWebSocketEventType.from(event);

            if (projectEventType != null) {
                projectEventHandler.handleProjectEvent(session, projectId, userId, projectEventType, raw);
            }
            else if(commentEventType != null) {
                commentEventHandler.handleCommentEvent(session, projectId, userId, commentEventType, raw);
            }
            else if(event.startsWith("TRACK_")){
                trackEventHandler.handleTrackEvent(session, projectId, event, raw);
            }
            else if(event.startsWith("CLIP_")){
                clipEventHandler.handleClipEvent(session, projectId, event, raw);
            }
            else if (event.startsWith("EQ_")) {
                eqEventHandler.handleEqEvent(session, projectId, event, raw);
            }
            else {
                webSocketMessageSender.sendError(session, 400, "지원하지 않는 이벤트입니다 : " + event);
            }
        } catch (BusinessException e) {
            webSocketMessageSender.sendError(session, e.getErrorCode().getStatus().value(), e.getMessage());
        } catch (Exception e) {
            log.error("[WS 처리 오류]", e);
            webSocketMessageSender.sendError(session, 500, "서버 오류가 발생했습니다.");
        } finally {
            SecurityContextHolder.clearContext();
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        Integer projectId = WebSocketSessionUtils.getProjectId(session);
        Integer userId = WebSocketSessionUtils.getUserId(session);

        sessionManager.remove(projectId, session);
        if (userId != null && !sessionManager.hasUserSession(projectId, userId)) {
            projectPresenceService.removeProjectUser(projectId, userId);
        }

        log.info("[WS 연결 종료]: session_id={}, project_id={}", session.getId(), projectId);
    }

    private void bindSecurityContext(Integer userId) {
        if (userId == null) {
            SecurityContextHolder.clearContext();
            return;
        }

        // WebSocket 처리 스레드에서도 JPA Auditing이 사용자 ID를 읽을 수 있도록 인증 컨텍스트를 주입
        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(String.valueOf(userId), null, List.of());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }
}
