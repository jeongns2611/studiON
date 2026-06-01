package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.track.dto.request.*;
import com.salmon.studion.domain.track.service.TrackService;
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
public class TrackEventHandler {

    private final WebSocketMessageSender webSocketMessageSender;
    private final ObjectMapper objectMapper;
    private final TrackService trackService;
    private final ProjectAutosaveScheduler projectAutosaveScheduler;

    public void handleTrackEvent(WebSocketSession session, Integer projectId, String event, WsMessage<Map> raw) throws IOException {
        Integer userId = WebSocketSessionUtils.getUserId(session);

        Object response = null;
        switch (event){
            case "TRACK_ADD":
                TrackAddRequest addRequest = bindTrackRequest(raw, TrackAddRequest.class, projectId);
                response = trackService.addTrack(addRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_DELETE":
                TrackRemoveRequest removeRequest = bindTrackRequest(raw, TrackRemoveRequest.class, projectId);
                response = trackService.removeTrack(removeRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_REORDER":
                TrackReorderRequest reorderRequest = bindTrackRequest(raw, TrackReorderRequest.class, projectId);
                response = trackService.reorderTrack(reorderRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_RENAME":
                TrackRenameRequest renameRequest = bindTrackRequest(raw, TrackRenameRequest.class, projectId);
                response = trackService.renameTrack(renameRequest, userId);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_SOLO_CHANGE":
                TrackSoloRequest soloRequest = bindTrackRequest(raw, TrackSoloRequest.class, projectId);
                response = trackService.soloTrack(soloRequest);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_MUTE_CHANGE":
                TrackMuteRequest muteRequest = bindTrackRequest(raw, TrackMuteRequest.class, projectId);
                response = trackService.muteTrack(muteRequest);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_VOLUME_CHANGE":
                TrackVolumeRequest volumeRequest = bindTrackRequest(raw, TrackVolumeRequest.class, projectId);
                response = trackService.changeVolume(volumeRequest);
                projectAutosaveScheduler.schedule(projectId);
                break;
            case "TRACK_PAN_CHANGE":
                TrackPanRequest panRequest = bindTrackRequest(raw, TrackPanRequest.class, projectId);
                response = trackService.changePan(panRequest);
                projectAutosaveScheduler.schedule(projectId);
                break;
            default:
                webSocketMessageSender.sendError(session, 400, "지원하지 않는 이벤트입니다.");
                return;
        }
        webSocketMessageSender.broadcast(projectId, event, response);
    }

    private <T extends TrackRequest> T bindTrackRequest(
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
