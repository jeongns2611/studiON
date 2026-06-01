package com.salmon.studion.domain.auth.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.auth.dto.request.OnboardingRequest;
import com.salmon.studion.domain.auth.dto.response.PositionDetailResponse;
import com.salmon.studion.domain.auth.entity.PositionDetail;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.entity.UserPosition;
import com.salmon.studion.domain.auth.repository.PositionDetailRepository;
import com.salmon.studion.domain.auth.repository.UserPositionRepository;
import com.salmon.studion.domain.auth.repository.UserRepository;
import com.salmon.studion.global.auth.PendingOAuthUserInfo;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Clock;
import java.util.List;

@Service
@RequiredArgsConstructor
public class UserService {

    private final StringRedisTemplate redisTemplate;
    private final UserPositionRepository userPositionRepository;
    private final UserRepository userRepository;
    private final PositionDetailRepository positionDetailRepository;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    // 포지션 상세 조회
    public List<PositionDetailResponse> getPositions() {
        return positionDetailRepository.findAllByOrderByPositionGroup_OrderAscOrderAsc()
                .stream()
                .map(positionDetail -> new PositionDetailResponse(
                        positionDetail.getCode(),
                        positionDetail.getName(),
                        positionDetail.getOrder(),
                        positionDetail.getPositionGroup().getCode(),
                        positionDetail.getPositionGroup().getName(),
                        positionDetail.getPositionGroup().getOrder()
                ))
                .toList();
    }

    @Transactional
    public User completeOnboarding(String onboardingSessionId, OnboardingRequest request) {
        String redisKey = "onboarding:" + onboardingSessionId;

        // 1. Redis 저장값과 대조 (토큰 재사용 방지)
        // 토큰 파싱/타입 검증 => JwtAuthenticationFilter에서 이미 처리
        String storedPayload = redisTemplate.opsForValue().get(redisKey);
        if(storedPayload == null) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "이미 사용되었거나 만료된 임시 토큰입니다.");
        }
        PendingOAuthUserInfo pendingOAuthUserInfo;
        try {
            pendingOAuthUserInfo = objectMapper.readValue(storedPayload, PendingOAuthUserInfo.class);
        } catch (JsonProcessingException e) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "임시 사용자 정보를 읽을 수 없습니다.");
        }
        if(userRepository.findByProviderAndProviderId(
                pendingOAuthUserInfo.provider(),
                pendingOAuthUserInfo.providerId()
        ).isPresent()) {
            redisTemplate.delete(redisKey);
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 가입된 사용자입니다.");
        }

        User user = userRepository.save(
                User.builder()
                        .email(pendingOAuthUserInfo.email())
                        .provider(pendingOAuthUserInfo.provider())
                        .providerId(pendingOAuthUserInfo.providerId())
                        .profileImgUrl(pendingOAuthUserInfo.profileImgUrl())
                        .nickname(pendingOAuthUserInfo.nickname())
                        .lastLoginAt(clock.instant())
                        .build()
        );

        // 3. 포지션 저장
        List<Integer> positionCodes = request.getPositionCodes();

        positionCodes.forEach(code -> {
            PositionDetail positionDetail = positionDetailRepository.findById(code)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "존재하지 않는 포지션 코드입니다.: " + code));

            userPositionRepository.save(UserPosition.of(user, positionDetail));
        });

        // 4. tmp token Redis에서 삭제 (재사용 불가)
        redisTemplate.delete(redisKey);
        return user;
    }

    public User getUserByUserId(Integer userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.USER_NOT_FOUND));
    }

    public List<User> getUsersByIds(List<Integer> mentionedUserIds) {
        return userRepository.findAllByIdIn(mentionedUserIds);
    }
}
