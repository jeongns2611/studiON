package com.salmon.studion.domain.project.facade;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.project.dto.redis.ProjectInviteRedisValue;
import com.salmon.studion.domain.project.dto.response.ProjectInvitationAcceptResponse;
import com.salmon.studion.domain.project.dto.response.ProjectInvitationCreateResponse;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.service.ProjectInviteService;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
@RequiredArgsConstructor
public class ProjectInviteFacade {

    private final UserService userService;
    private final ProjectService projectService;
    private final ProjectMemberService projectMemberService;
    private final ProjectInviteService projectInviteService;

    public ProjectInvitationCreateResponse createOrRefreshInvitation(Integer projectId, Integer userId) {
        projectService.getProjectOrThrow(projectId);
        projectMemberService.validateProjectMember(projectId, userId);

        return projectInviteService.createOrRefreshInvitation(projectId, userId);
    }

    @Transactional
    public ProjectInvitationAcceptResponse acceptInvitation(String inviteCode, Integer userId) {
        ProjectInviteRedisValue invitation = projectInviteService.getValidInvitation(inviteCode);
        Integer projectId = invitation.projectId();

        Project project = projectService.getProjectOrThrow(projectId);
        User user = userService.getUserByUserId(userId);
        
        // TODO: 추후 레디스 락 방식으로 변경 예정
        if (projectMemberService.isProjectMember(projectId, userId)) {
           throw new BusinessException(ErrorCode.PROJECT_MEMBER_ALREADY_EXISTS);
        }

        // TODO: 유저테스트 전용 임시 구현 (추후 수정 필요 - validateProjectMemberLimit())
        projectMemberService.validateProjectMemberLimit(projectId);

        projectMemberService.createProjectMember(project, user);

        return ProjectInvitationAcceptResponse.of(projectId);
    }
}
