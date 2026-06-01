package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.clip.dto.request.*;
import com.salmon.studion.domain.clip.service.ClipService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
import com.salmon.studion.global.infrastructure.websocket.util.WebSocketSessionUtils;
import com.salmon.studion.global.scheduler.ProjectAutosaveScheduler;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Slf4j
@Component
@RequiredArgsConstructor
public class ClipEventHandler {
    private final WebSocketMessageSender webSocketMessageSender;
    private final ObjectMapper objectMapper;
    private final ClipService clipService;
    private final ProjectAutosaveScheduler projectAutosaveScheduler;

    public void handleClipEvent(WebSocketSession session, Integer projectId, String event, WsMessage<Map> raw) throws IOException {
        Integer userId = WebSocketSessionUtils.getUserId(session);

        Object response = null;
        switch (event){
            case "CLIP_CREATE":
                ClipCreateRequest createRequest = bindClipRequest(raw, ClipCreateRequest.class, projectId);
                response = clipService.createClip(createRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_LOCK":
                ClipLockRequest lockRequest = bindClipRequest(raw, ClipLockRequest.class, projectId);
                response = clipService.lockClip(lockRequest, userId);
                break;
            case "CLIP_MOVE":
                ClipMoveRequest moveRequest = bindClipRequest(raw, ClipMoveRequest.class, projectId);
                response = clipService.moveClip(moveRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_RESIZE":
                ClipResizeRequest resizeRequest = bindClipRequest(raw, ClipResizeRequest.class, projectId);
                response = clipService.resizeClip(resizeRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_SPLIT":
                ClipSplitRequest splitRequest = bindClipRequest(raw, ClipSplitRequest.class, projectId);
                response = clipService.splitClip(splitRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_DUPLICATE":
                ClipDuplicateRequest duplicateRequest = bindClipRequest(raw, ClipDuplicateRequest.class, projectId);
                response = clipService.duplicateClip(duplicateRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_CUT":
                ClipCutRequest cutRequest = bindClipRequest(raw, ClipCutRequest.class, projectId);
                response = clipService.cutClip(cutRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_COPY":
                ClipCopyRequest copyRequest = bindClipRequest(raw, ClipCopyRequest.class, projectId);
                response = clipService.copyClip(copyRequest, userId);
                webSocketMessageSender.sendToSession(session, event, response);
                return;
            case "CLIP_PASTE":
                ClipPasteRequest pasteRequest = bindClipRequest(raw, ClipPasteRequest.class, projectId);
                response = clipService.pasteClip(pasteRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "CLIP_DELETE":
                ClipDeleteRequest deleteRequest = bindClipRequest(raw, ClipDeleteRequest.class, projectId);
                response = clipService.deleteClip(deleteRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            default:
                webSocketMessageSender.sendError(session, 400, "지원하지 않는 이벤트입니다.");
                return;
        }
        webSocketMessageSender.broadcast(projectId, event, response);

    }

    private <T extends ClipRequest> T bindClipRequest(
            WsMessage<Map> raw,
            Class<T> requestType,
            Integer pathProjectId
    ) {
        T request = objectMapper.convertValue(raw.getPayload(), requestType);

        Integer payloadProjectId = request.getProjectId();
        if (payloadProjectId != null && !pathProjectId.equals(payloadProjectId)) {
            // TODO: enum 코드 값으로 분리하기
            throw new BusinessException(
                    ErrorCode.INVALID_REQUEST,
                    "WebSocket 경로의 projectId와 payload의 projectId가 일치하지 않습니다."
            );
        }

        request.setProjectId(pathProjectId);
        return request;
    }

}
