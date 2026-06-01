package com.salmon.studion.domain.auth.dto.response;

import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class TokenResponse {

    private boolean isNewUser;
    private String accessToken;
}
