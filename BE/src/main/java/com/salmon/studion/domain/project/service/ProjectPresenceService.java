package com.salmon.studion.domain.project.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.project.dto.websocket.ProjectOnlineUserResponse;
import com.salmon.studion.domain.project.dto.websocket.ProjectPresenceRegistration;
import com.salmon.studion.domain.project.dto.websocket.ProjectPresenceUserInfo;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.HashOperations;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.io.UncheckedIOException;
import java.time.Clock;
import java.util.Comparator;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ProjectPresenceService {

    private static final String PROJECT_PRESENCE_KEY = "presence:project:%d";

    private final RedisTemplate<String, String> redisTemplate;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public ProjectPresenceRegistration registerProjectUser(Integer projectId, User user) {
        HashOperations<String, Object, Object> hashOperations = redisTemplate.opsForHash();
        String key = presenceKey(projectId);
        String field = String.valueOf(user.getId());
        ProjectPresenceUserInfo presenceUserInfo = ProjectPresenceUserInfo.from(user, clock.instant());
        String serializedValue = serialize(presenceUserInfo);

        Boolean inserted = hashOperations.putIfAbsent(key, field, serializedValue);
        if (Boolean.TRUE.equals(inserted)) {
            return new ProjectPresenceRegistration(presenceUserInfo, true);
        }

        Object existingValue = hashOperations.get(key, field);
        if (existingValue instanceof String value) {
            return new ProjectPresenceRegistration(deserialize(value), false);
        }

        hashOperations.put(key, field, serializedValue);
        return new ProjectPresenceRegistration(presenceUserInfo, false);
    }

    public List<ProjectOnlineUserResponse> getOnlineUsers(Integer projectId) {
        List<Object> values = redisTemplate.opsForHash().values(presenceKey(projectId));
        return values.stream()
                .filter(String.class::isInstance)
                .map(String.class::cast)
                .map(this::deserialize)
                .sorted(Comparator.comparing(ProjectPresenceUserInfo::joinedAt))
                .map(ProjectPresenceUserInfo::toOnlineUserResponse)
                .toList();
    }

    public boolean removeProjectUser(Integer projectId, Integer userId) {
        Long deletedCount = redisTemplate.opsForHash().delete(presenceKey(projectId), String.valueOf(userId));

        return deletedCount != null && deletedCount > 0;
    }

    private String presenceKey(Integer projectId) {
        return PROJECT_PRESENCE_KEY.formatted(projectId);
    }

    private String serialize(ProjectPresenceUserInfo userInfo) {
        try {
            return objectMapper.writeValueAsString(userInfo);
        } catch (JsonProcessingException e) {
            throw new UncheckedIOException(e);
        }
    }

    private ProjectPresenceUserInfo deserialize(String value) {
        try {
            return objectMapper.readValue(value, ProjectPresenceUserInfo.class);
        } catch (JsonProcessingException e) {
            throw new BusinessException(ErrorCode.INTERNAL_SERVER_ERROR, "프로젝트 접속자 정보를 읽는 중 오류가 발생했습니다.");
        }
    }
}
