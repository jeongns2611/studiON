package com.salmon.studion.global.infrastructure.websocket.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.project.dto.websocket.*;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.project.service.ProjectPresenceService;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.global.common.enums.ProjectWebSocketEventType;
import com.salmon.studion.global.infrastructure.websocket.ProjectSessionManager;
import com.salmon.studion.global.infrastructure.websocket.ProjectWebSocketBroadcaster;
import com.salmon.studion.global.infrastructure.websocket.WebSocketMessageSender;
import com.salmon.studion.global.infrastructure.websocket.common.WsMessage;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

import java.io.IOException;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class ProjectEventHandler {

    private final ObjectMapper objectMapper;
    private final UserService userService;
    private final ProjectService projectService;
    private final ProjectMemberService projectMemberService;
    private final ProjectPresenceService projectPresenceService;
    private final ProjectWebSocketBroadcaster projectWebSocketBroadcaster;
    private final WebSocketMessageSender webSocketMessageSender;
    private final ProjectSessionManager sessionManager;

    public void handleProjectEvent(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            ProjectWebSocketEventType eventType,
            WsMessage<Map> raw
    ) throws IOException {
        switch (eventType) {
            case PROJECT_JOIN ->  projectJoin(session, projectId, userId, raw);
            case PROJECT_LEFT ->  projectLeft(session, projectId, userId, raw);
            case PROJECT_RENAME -> projectRename(session, projectId, userId, raw);
            case PROJECT_TIME_SIGNATURE -> projectTimeSignature(session, projectId, userId, raw);
            case PROJECT_KEY -> projectKey(session, projectId, userId, raw);
            case PROJECT_BPM -> projectBpm(session, projectId, userId, raw);

            case PROJECT_ONLINE_USERS,
                 USER_JOINED_PROJECT,
                 USER_LEFT_PROJECT,
                 PROJECT_RENAMED,
                 MODIFIED_PROJECT_TIME_SIGNATURE,
                 MODIFIED_PROJECT_KEY,
                 MODIFIED_PROJECT_BPM -> {
                webSocketMessageSender.sendError(session, 400, "클라이언트에서 직접 보낼 수 없는 프로젝트 이벤트입니다.");
            }

            default -> webSocketMessageSender.sendError(session, 400, "지원하지 않는 프로젝트 이벤트입니다.");
        }
    }

    private void projectJoin(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        projectMemberService.validateProjectMember(projectId, userId);

        User user = userService.getUserByUserId(userId);
        ProjectPresenceRegistration registration = projectPresenceService.registerProjectUser(projectId, user);

        sendOnlineUsers(session, projectId);

        if (registration.newlyJoined()) {
            projectWebSocketBroadcaster.broadcastToProjectExceptSession(
                    projectId,
                    session.getId(),
                    ProjectWebSocketEventType.USER_JOINED_PROJECT,
                    new ProjectUserJoinedResponse(
                            projectId,
                            registration.user().toOnlineUserResponse()
                    )
            );
        }
    }

    private void projectLeft(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        projectMemberService.validateProjectMember(projectId, userId);

        try {
            sessionManager.remove(projectId, session);
            boolean hasRemainingSession = userId != null && sessionManager.hasUserSession(projectId, userId);

            if (hasRemainingSession) {
                return;
            }

            boolean actuallyLeft = projectPresenceService.removeProjectUser(projectId, userId);
            if (!actuallyLeft) {
                return;
            }

            projectWebSocketBroadcaster.broadcastToProject(
                    projectId,
                    ProjectWebSocketEventType.USER_LEFT_PROJECT,
                    new ProjectUserLeftResponse(userId)
            );
        } finally {
            session.close();
        }
    }

    private void projectRename(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        ProjectRenameRequest request = objectMapper.convertValue(raw.getPayload(), ProjectRenameRequest.class);

        projectMemberService.validateProjectMember(projectId, userId);

        String renamedProjectName = projectService.renameProject(projectId, request.name());

        projectWebSocketBroadcaster.broadcastToProject(
                projectId,
                ProjectWebSocketEventType.PROJECT_RENAMED,
                new ProjectRenamedResponse(renamedProjectName)
        );
    }

    private void sendOnlineUsers(WebSocketSession session, Integer projectId) throws IOException {
        webSocketMessageSender.sendToSession(
                session,
                ProjectWebSocketEventType.PROJECT_ONLINE_USERS.name(),
                new ProjectOnlineUsersResponse(
                        projectId,
                        projectPresenceService.getOnlineUsers(projectId)
                )
        );
    }

    private void projectBpm(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        ProjectBpmRequest request = objectMapper.convertValue(raw.getPayload(), ProjectBpmRequest.class);

        projectMemberService.validateProjectMember(projectId, userId);

        Double tempo = projectService.changeTempo(projectId, request.tempo());

        projectWebSocketBroadcaster.broadcastToProject(
                projectId,
                ProjectWebSocketEventType.MODIFIED_PROJECT_BPM,
                new ProjectBpmModifiedResponse(tempo)
        );
    }

    private void projectKey(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        ProjectKeyRequest request = objectMapper.convertValue(raw.getPayload(), ProjectKeyRequest.class);

        projectMemberService.validateProjectMember(projectId, userId);

        Project updated = projectService.changeKey(projectId, request.rootNote(), request.mode());

        projectWebSocketBroadcaster.broadcastToProject(
                projectId,
                ProjectWebSocketEventType.MODIFIED_PROJECT_KEY,
                new ProjectKeyModifiedResponse(updated.getRootNote(), updated.getMode())
        );
    }

    private void projectTimeSignature(
            WebSocketSession session,
            Integer projectId,
            Integer userId,
            WsMessage<Map> raw
    ) throws IOException {
        ProjectTimeSignatureRequest request = objectMapper.convertValue(raw.getPayload(), ProjectTimeSignatureRequest.class);

        projectMemberService.validateProjectMember(projectId, userId);

        Project updated = projectService.changeTimeSignature(projectId, request.timeSigNumerator(), request.timeSigDenominator());

        projectWebSocketBroadcaster.broadcastToProject(
                projectId,
                ProjectWebSocketEventType.MODIFIED_PROJECT_TIME_SIGNATURE,
                new ProjectTimeSignatureModifiedResponse(updated.getTimeSigNumerator(), updated.getTimeSigDenominator())
        );
    }

}
