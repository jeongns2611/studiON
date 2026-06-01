package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.project.dto.redis.ProjectInviteRedisValue;
import com.salmon.studion.domain.project.dto.response.ProjectInvitationCreateResponse;
import com.salmon.studion.domain.project.repository.ProjectInviteRedisRepository;
import com.salmon.studion.domain.project.support.ProjectInviteCodeGenerator;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;

@Service
@RequiredArgsConstructor
public class ProjectInviteService {

    private static final int INVITE_CODE_EXPIRATION_MINUTES = 5;
    private static final int INVITE_CODE_TTL_MINUTES = 10;
    private static final int MAX_INVITE_CODE_GENERATION_RETRY = 50;

    private final ProjectInviteRedisRepository projectInviteRedisRepository;
    private final ProjectInviteCodeGenerator projectInviteCodeGenerator;
    private final Clock clock;
//    private final ProjectInviteRateLimiter projectInviteRateLimiter;
//    private final ProjectInviteLockManager projectInviteLockManager;

    public ProjectInvitationCreateResponse createOrRefreshInvitation(Integer projectId, Integer userId) {
        projectInviteRedisRepository.deleteActiveInviteByProjectId(projectId);

        String inviteCode = generateUniqueInviteCode();
        Instant expiresAt = clock.instant().plusSeconds(INVITE_CODE_EXPIRATION_MINUTES * 60L);
        Duration ttl = Duration.ofMinutes(INVITE_CODE_TTL_MINUTES);

        ProjectInviteRedisValue value = new ProjectInviteRedisValue(projectId, inviteCode, userId, expiresAt);

        projectInviteRedisRepository.save(value, ttl);

        return ProjectInvitationCreateResponse.of(projectId, inviteCode, expiresAt);
    }

    public ProjectInviteRedisValue getValidInvitation(String inviteCode) {
        ProjectInviteRedisValue invitation  = projectInviteRedisRepository.findByInviteCode(inviteCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.PROJECT_INVITE_CODE_INVALID));

        if (invitation.isExpired(clock.instant())) {
            throw new BusinessException(ErrorCode.PROJECT_INVITE_CODE_EXPIRED);
        }

        return invitation;
    }

    private String generateUniqueInviteCode() {
        for (int i=0; i<MAX_INVITE_CODE_GENERATION_RETRY; i++) {
            String code = projectInviteCodeGenerator.generate();
            
            if (!projectInviteRedisRepository.existsByInviteCode(code)) {
                return code;
            }
        }

        throw new BusinessException(ErrorCode.PROJECT_INVITE_CODE_GENERATION_FAILED);
    }

    public void deleteByInviteCode(String inviteCode) {
        projectInviteRedisRepository.deleteByInviteCode(inviteCode);
    }
}
