package com.salmon.studion.domain.project.dto.websocket;

import com.salmon.studion.domain.auth.entity.User;

import java.time.Instant;

public record ProjectPresenceUserInfo(
        Integer userId,
        String nickname,
        String profileImageUrl,
        Instant joinedAt
) {

    public static ProjectPresenceUserInfo from(User user, Instant joinedAt) {
        return new ProjectPresenceUserInfo(
                user.getId(),
                user.getNickname(),
                user.getProfileImgUrl(),
                joinedAt
        );
    }

    public ProjectOnlineUserResponse toOnlineUserResponse() {
        return new ProjectOnlineUserResponse(userId, nickname, profileImageUrl);
    }
}
