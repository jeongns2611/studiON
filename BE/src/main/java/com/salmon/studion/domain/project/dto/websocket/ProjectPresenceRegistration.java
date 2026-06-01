package com.salmon.studion.domain.project.dto.websocket;

public record ProjectPresenceRegistration(
        ProjectPresenceUserInfo user,
        boolean newlyJoined
) {
}
