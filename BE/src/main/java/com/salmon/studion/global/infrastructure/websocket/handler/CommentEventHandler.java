package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.comment.dto.websocket.CommentCreateRequest;
import com.salmon.studion.domain.comment.dto.websocket.CommentDeleteRequest;
import com.salmon.studion.domain.comment.dto.websocket.CommentStatusChangeRequest;
import com.salmon.studion.domain.comment.facade.CommentFacade;
import com.salmon.studion.global.common.enums.CommentWebSocketEventType;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
import com.salmon.studion.global.scheduler.ProjectAutosaveScheduler;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class CommentEventHandler {

    private final ObjectMapper objectMapper;
    private final CommentFacade commentFacade;
    private final WebSocketMessageSender webSocketMessageSender;
    private final ProjectAutosaveScheduler projectAutosaveScheduler;

    public void handleCommentEvent(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            CommentWebSocketEventType eventType,
            WsMessage<Map> raw
    ) throws IOException {

        switch (eventType) {
            case COMMENT_ADD -> {
                CommentCreateRequest request = objectMapper.convertValue(raw.getPayload(), CommentCreateRequest.class);
                request.setProjectId(projectId);
                Object response = commentFacade.createComment(request, userId);
                webSocketMessageSender.broadcast(projectId, CommentWebSocketEventType.COMMENT_ADDED.name(), response);
                projectAutosaveScheduler.schedule(projectId);
            }
            case COMMENT_DELETE -> {
                CommentDeleteRequest request = objectMapper.convertValue(raw.getPayload(), CommentDeleteRequest.class);
                request.setProjectId(projectId);
                Object response = commentFacade.deleteComment(request, userId);
                webSocketMessageSender.broadcast(projectId, CommentWebSocketEventType.COMMENT_DELETED.name(), response);
                projectAutosaveScheduler.schedule(projectId);
            }
            case COMMENT_STATUS_CHANGE -> {
                CommentStatusChangeRequest request = objectMapper.convertValue(raw.getPayload(), CommentStatusChangeRequest.class);
                request.setProjectId(projectId);
                Object response = commentFacade.changeStatus(request, userId);
                webSocketMessageSender.broadcast(projectId, CommentWebSocketEventType.COMMENT_STATUS_CHANGED.name(), response);
                projectAutosaveScheduler.schedule(projectId);
            }

            case COMMENT_ADDED,
                 COMMENT_DELETED,
                 COMMENT_STATUS_CHANGED -> {
                webSocketMessageSender.sendError(session, 400, "클라이언트에서 직접 보낼 수 없는 코멘트 이벤트입니다.");
            }

            default -> webSocketMessageSender.sendError(session, 400, "지원하지 않는 코멘트 이벤트입니다.");
        }
    }
}
