package com.salmon.studion.global.auth;

public record PendingOAuthUserInfo(
        String email,
        String provider,
        String providerId,
        String profileImgUrl,
        String nickname
) {
}
