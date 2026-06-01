package com.salmon.studion.domain.auth.dto.request;

import jakarta.validation.constraints.NotEmpty;
import lombok.Getter;

import java.util.List;

@Getter
public class OnboardingRequest {
    // 무좍건 포지션 입력해야 회원가입 되도록
    @NotEmpty(message = "포지션을 1개 이상 선택해주세요.")
    private List<Integer> positionCodes;
}
