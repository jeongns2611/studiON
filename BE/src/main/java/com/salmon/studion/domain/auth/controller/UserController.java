package com.salmon.studion.domain.auth.controller;

import com.salmon.studion.domain.auth.dto.request.OnboardingRequest;
import com.salmon.studion.domain.auth.dto.response.PositionDetailResponse;
import com.salmon.studion.domain.auth.dto.response.TokenResponse;
import com.salmon.studion.domain.auth.entity.PositionDetail;
import com.salmon.studion.domain.auth.entity.PositionGroup;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.global.auth.JwtTokenProvider;
import com.salmon.studion.global.common.response.ApiResponse;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class UserController {

    private final JwtTokenProvider jwtTokenProvider;
    private final UserService userService;
    private final StringRedisTemplate redisTemplate;

    @Value("${spring.jwt.refresh-expiration}")
    long refreshTokenExpiration;

    // 선택한 그룹의 포지션 상세 목록 조회
    @GetMapping("/positions")
    public ResponseEntity<ApiResponse<List<PositionDetailResponse>>> getPositions() {
        return ResponseEntity.ok(ApiResponse.success(userService.getPositions()));
    }

    // 온보딩 완료 (ONBOARDING_SESSION 쿠키로 임시 OAuth 정보를 조회한 뒤 정식 토큰 발급)
    @PostMapping("/onboarding")
    public ResponseEntity<ApiResponse<TokenResponse>> completeOnboarding(
            @CookieValue(value = "ONBOARDING_SESSION", required = false) String onboardingSessionId,
            @RequestBody @Valid OnboardingRequest request,
            HttpServletResponse servletResponse
            ) {
        if(onboardingSessionId == null || onboardingSessionId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "온보딩 세션이 없습니다.");
        }

        User user = userService.completeOnboarding(onboardingSessionId, request);

        String accessToken = jwtTokenProvider.generateAccessToken(user.getId());
        String refreshToken = jwtTokenProvider.generateRefreshToken(user.getId());

        // refresh token을 Redis에 저장하면서 만료 시간 TTL 설정
        redisTemplate.opsForValue().set(
                "refresh:" + user.getId(),
                refreshToken,
                refreshTokenExpiration,
                TimeUnit.MILLISECONDS
        );

        ResponseCookie deleteOnboardingCookie =
                ResponseCookie.from("ONBOARDING_SESSION", "")
                        .httpOnly(true)
                        .secure(true)
                        .sameSite("Lax")
                        .path("/api/v1/auth/onboarding")
                        .maxAge(0)
                        .build();

        servletResponse.addHeader(HttpHeaders.SET_COOKIE, deleteOnboardingCookie.toString());

        ResponseCookie refreshCookie = ResponseCookie.from("REFRESH_TOKEN", refreshToken)
                .httpOnly(true)
                .secure(true)
                .sameSite("Lax")
                .path("/api/v1/auth")
                .maxAge(refreshTokenExpiration / 1000)
                .build();

        servletResponse.addHeader(HttpHeaders.SET_COOKIE, refreshCookie.toString());

        // 정식 토큰 발급
        TokenResponse response = TokenResponse.builder()
                .isNewUser(false)
                .accessToken(accessToken)
                .build();

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    // 프론트 => url에서 code 읽고 이 API 호출 -> access token 발급받음
    @PostMapping("/exchange")
    public ResponseEntity<ApiResponse<TokenResponse>> exchangeLoginCode(
            @RequestParam String code
    ) {

        String redisKey = "login-code:" + code;

        String userIdValue = redisTemplate.opsForValue().getAndDelete(redisKey);
        if(userIdValue == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "만료되었거나 잘못된 로그인 코드입니다.");
        }

        Integer userId = Integer.valueOf(userIdValue);
        String accessToken = jwtTokenProvider.generateAccessToken(userId);

        TokenResponse response = TokenResponse.builder()
                .isNewUser(false)
                .accessToken(accessToken)
                .build();

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    // access token 재발급
    @PostMapping("/reissue")
    public ResponseEntity<ApiResponse<TokenResponse>> reissue(
            @CookieValue(value="REFRESH_TOKEN", required = false) String refreshToken,
            HttpServletResponse servletResponse
    ) {
        if(refreshToken == null || refreshToken.isBlank()) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "refresh token이 없습니다.");
        }

        jwtTokenProvider.validateTokenType(refreshToken, "REFRESH");

        Integer userId = jwtTokenProvider.getUserIdFromToken(refreshToken);

        String redisKey = "refresh:" + userId;
        String storedRefreshToken = redisTemplate.opsForValue().get(redisKey);

        if(storedRefreshToken == null || !storedRefreshToken.equals(refreshToken)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "유효하지 않은 refresh token입니다.");
        }

        String newAccessToken = jwtTokenProvider.generateAccessToken(userId);
        String newRefreshToken = jwtTokenProvider.generateRefreshToken(userId);

        // refresh token rotation: access token 재발급 시 refresh token도 새 값으로 교체
        redisTemplate.opsForValue().set(
                redisKey,
                newRefreshToken,
                refreshTokenExpiration,
                TimeUnit.MILLISECONDS
        );

        ResponseCookie refreshCookie = ResponseCookie.from("REFRESH_TOKEN", newRefreshToken)
                .httpOnly(true)
                .secure(true)
                .sameSite("Lax")
                .path("/api/v1/auth")
                .maxAge(refreshTokenExpiration / 1000)
                .build();

        servletResponse.addHeader(HttpHeaders.SET_COOKIE, refreshCookie.toString());

        TokenResponse response = TokenResponse.builder()
                .isNewUser(false)
                .accessToken(newAccessToken)
                .build();

        return ResponseEntity.ok(ApiResponse.success(response));
    }

    // 로그아웃: 서버에 저장된 refresh token을 제거하고 브라우저 쿠키도 만료시킨다.
    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(
            @CookieValue(value = "REFRESH_TOKEN", required = false) String refreshToken,
            HttpServletResponse servletResponse
    ) {
        if(refreshToken != null && !refreshToken.isBlank()) {
            try {
                jwtTokenProvider.validateTokenType(refreshToken, "REFRESH");
                Integer userId = jwtTokenProvider.getUserIdFromToken(refreshToken);
                redisTemplate.delete("refresh:" + userId);
            } catch (Exception ignored) {
                // 쿠키가 유효하지 않아도 클라이언트 쿠키는 제거해서 로그아웃 상태로 만든다.
            }
        }

        ResponseCookie deleteRefreshCookie = ResponseCookie.from("REFRESH_TOKEN", "")
                .httpOnly(true)
                .secure(true)
                .sameSite("Lax")
                .path("/api/v1/auth")
                .maxAge(0)
                .build();

        servletResponse.addHeader(HttpHeaders.SET_COOKIE, deleteRefreshCookie.toString());

        return ResponseEntity.ok(ApiResponse.success());
    }
}
