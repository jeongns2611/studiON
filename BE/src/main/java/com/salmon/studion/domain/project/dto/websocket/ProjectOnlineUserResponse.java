package com.salmon.studion.domain.project.dto.websocket;

public record ProjectOnlineUserResponse(
        Integer userId,
        String nickname,
        String profileImageUrl
) {
}
