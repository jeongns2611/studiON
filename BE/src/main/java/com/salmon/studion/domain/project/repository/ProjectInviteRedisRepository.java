package com.salmon.studion.domain.project.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.project.dto.redis.ProjectInviteRedisValue;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Repository;

import java.time.Duration;
import java.util.Optional;

@Repository
@RequiredArgsConstructor
public class ProjectInviteRedisRepository {

    private static final String INVITE_CODE_KEY = "invite:code:%s";     // invite:code:{inviteCode}
    private static final String ACTIVE_INVITE_KEY = "invite:project:%d:code";  // invite:project:{projectId}:code

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;

    public void save(ProjectInviteRedisValue value, Duration ttl) {
        String inviteCodeKey = inviteCodeKey(value.inviteCode());
        String activeInviteKey = activeInviteKey(value.projectId());

        String serializedValue = serialize(value);

        redisTemplate.opsForValue().set(inviteCodeKey, serializedValue, ttl);
        redisTemplate.opsForValue().set(activeInviteKey, value.inviteCode(), ttl);
    }

    public Optional<ProjectInviteRedisValue> findByInviteCode(String inviteCode) {
        String storedValue = redisTemplate.opsForValue().get(inviteCodeKey(inviteCode));

        if (storedValue == null) {
            return Optional.empty();
        }

        return Optional.of(deserialize(storedValue));
    }

    public Optional<String> findActiveInviteCodeByProjectId(Integer projectId) {
        return Optional.ofNullable(redisTemplate.opsForValue().get(activeInviteKey(projectId)));
    }
    
    public boolean existsByInviteCode(String inviteCode) {
        return Boolean.TRUE.equals(redisTemplate.hasKey(inviteCodeKey(inviteCode)));
    }
    
    public void deleteByInviteCode(String inviteCode) {
        findByInviteCode(inviteCode).ifPresent(value -> {
            redisTemplate.delete(inviteCodeKey(inviteCode));
            
            String activeKey = activeInviteKey(value.projectId());
            String activeInviteCode = redisTemplate.opsForValue().get(activeKey);
            
            if (inviteCode.equals(activeInviteCode)) {
                redisTemplate.delete(activeKey);
            }
        });
    }

    public void deleteActiveInviteByProjectId(Integer projectId) {
        String activeKey = activeInviteKey(projectId);
        String activeInviteCode = redisTemplate.opsForValue().get(activeKey);

        if (activeInviteCode != null) {
            redisTemplate.delete(inviteCodeKey(activeInviteCode));
            redisTemplate.delete(activeKey);
        }
    }
    
    private String serialize(ProjectInviteRedisValue value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            // TODO: ErrorCode 타입으로 빼기
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "프로젝트 초대 코드 직렬화에 실패했습니다.");
        }
    }

    private ProjectInviteRedisValue deserialize(String value) {
        try {
            return objectMapper.readValue(value, ProjectInviteRedisValue.class);
        } catch (JsonProcessingException e) {
            // TODO: ErrorCode 타입으로 빼기
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "프로젝트 초대 코드 역직렬화에 실패했습니다.");
        }
    }
    
    private String inviteCodeKey(String inviteCode) {
        return INVITE_CODE_KEY.formatted(inviteCode);
    }
    
    private String activeInviteKey(Integer projectId) {
        return ACTIVE_INVITE_KEY.formatted(projectId);
    }
}
