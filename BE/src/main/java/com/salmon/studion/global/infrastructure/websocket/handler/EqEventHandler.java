package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.eq.dto.request.TrackEqCommitRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqDraftSaveRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqLockRequest;
import com.salmon.studion.domain.eq.dto.request.TrackEqResetRequest;
import com.salmon.studion.domain.eq.service.TrackEqService;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
import com.salmon.studion.global.infrastructure.websocket.util.WebSocketSessionUtils;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class EqEventHandler {

    private final WebSocketMessageSender webSocketMessageSender;
    private final ObjectMapper objectMapper;
    private final TrackEqService trackEqService;

    public void handleEqEvent(WebSocketSession session, Integer projectId, String event, WsMessage<Map> raw) throws IOException {
        Integer userId = WebSocketSessionUtils.getUserId(session);

        Object response;

        switch (event) {
            case "EQ_LOCK":
                TrackEqLockRequest lockRequest = objectMapper.convertValue(raw.getPayload(), TrackEqLockRequest.class);
                response = trackEqService.lockTrackEq(lockRequest, userId);
                break;
            case "EQ_DRAFT_SAVE":
                TrackEqDraftSaveRequest draftSaveRequest = objectMapper.convertValue(raw.getPayload(), TrackEqDraftSaveRequest.class);
                response = trackEqService.saveDraft(draftSaveRequest, userId);
                break;
            case "EQ_RESET":
                TrackEqResetRequest resetRequest = objectMapper.convertValue(raw.getPayload(), TrackEqResetRequest.class);
                response = trackEqService.resetDraft(resetRequest, userId);
                break;
            case "EQ_COMMIT":
                TrackEqCommitRequest commitRequest = objectMapper.convertValue(raw.getPayload(), TrackEqCommitRequest.class);
                response = trackEqService.commitDraft(commitRequest, userId);
                break;
            default:
                webSocketMessageSender.sendError(session, 400, "지원하지 않는 EQ 이벤트입니다.");
                return;
        }

        webSocketMessageSender.broadcast(projectId, event, response);
    }
}
