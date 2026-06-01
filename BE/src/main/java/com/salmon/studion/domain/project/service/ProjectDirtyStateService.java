package com.salmon.studion.domain.project.service;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ProjectDirtyStateService {

    private static final String DIRTY_PROJECTS_KEY = "autosave:dirty:projects";
    private static final String LAST_EVENT_AT_KEY = "autosave:last-event-at:%d";
    private static final String SAVING_KEY = "autosave:saving:%d";
    private static final String FAIL_COUNT_KEY = "autosave:fail-count:%d";
    private static final String LAST_SAVED_AT_KEY = "autosave:last-saved-at:%d";

    private static final Duration SAVING_LOCK_TTL = Duration.ofSeconds(60*5);
    private static final Duration KEY_TTL = Duration.ofHours(2);

    private final RedisTemplate<String, String> redisTemplate;

    public void markDirty(Integer projectId) {
        redisTemplate.opsForSet().add(DIRTY_PROJECTS_KEY, String.valueOf(projectId));
        redisTemplate.opsForValue().set(
                String.format(LAST_EVENT_AT_KEY, projectId),
                String.valueOf(System.currentTimeMillis()),
                KEY_TTL
        );
    }

    public boolean isDirty(Integer projectId) {
        return Boolean.TRUE.equals(redisTemplate.opsForSet().isMember(DIRTY_PROJECTS_KEY, String.valueOf(projectId)));
    }

    public Set<Integer> getDirtyProjectIds() {
        Set<String> rawIds = redisTemplate.opsForSet().members(DIRTY_PROJECTS_KEY);
        if (rawIds == null || rawIds.isEmpty()) {
            return Set.of();
        }
        return rawIds.stream()
                .map(Integer::parseInt)
                .collect(Collectors.toSet());
    }

    public boolean acquireSavingLock(Integer projectId) {
        Boolean result = redisTemplate.opsForValue().setIfAbsent(
                String.format(SAVING_KEY, projectId),
                "1",
                SAVING_LOCK_TTL
        );
        return Boolean.TRUE.equals(result);
    }

    public void releaseSavingLock(Integer projectId) {
        redisTemplate.delete(String.format(SAVING_KEY, projectId));
    }

    public void markSaveSuccess(Integer projectId) {
        redisTemplate.opsForSet().remove(DIRTY_PROJECTS_KEY, String.valueOf(projectId));
        redisTemplate.delete(String.format(LAST_EVENT_AT_KEY, projectId));
        redisTemplate.delete(String.format(FAIL_COUNT_KEY, projectId));
        redisTemplate.opsForValue().set(
                String.format(LAST_SAVED_AT_KEY, projectId),
                String.valueOf(System.currentTimeMillis()),
                KEY_TTL
        );
    }

    public long incrementFailCount(Integer projectId) {
        String key = String.format(FAIL_COUNT_KEY, projectId);
        Long value = redisTemplate.opsForValue().increment(key);
        redisTemplate.expire(key, KEY_TTL);
        return value == null ? 0L : value;
    }

    public long getFailCount(Integer projectId) {
        String value = redisTemplate.opsForValue().get(String.format(FAIL_COUNT_KEY, projectId));
        if (value == null) {
            return 0L;
        }
        return Long.parseLong(value);
    }
}
