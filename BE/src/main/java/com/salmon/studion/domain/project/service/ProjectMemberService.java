package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.entity.ProjectMember;
import com.salmon.studion.domain.project.repository.ProjectMemberRepository;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ProjectMemberService {

    private final ProjectMemberRepository projectMemberRepository;

    // TODO: 유저테스트 전용 임시 구현 (추후 수정 필요 - TEM_MAX_PROJECT_MEMBER_COUNT)
    private static final long TEMP_MAX_PROJECT_MEMBER_COUNT = 6L;

    public void createProjectMember(Project project, User user) {
        try {
            projectMemberRepository.save(ProjectMember.create(project, user));
        } catch (DataIntegrityViolationException e) {
            throw new BusinessException(ErrorCode.PROJECT_MEMBER_ALREADY_EXISTS);
        }
    }

    public List<Integer> getProjectIdsByUserId(Integer userId) {
        return projectMemberRepository.findProjectIdsByUserId(userId);
    }

    public List<ProjectMember> getMembersWithUserByProjectIds(List<Integer> projectIds) {
        if (projectIds.isEmpty())
            return List.of();

        return projectMemberRepository.findAllWithUserByProjectIdIn(projectIds);
    }

    public void validateProjectMember(Integer projectId, Integer userId) {
        if (!projectMemberRepository.existsByProject_IdAndUser_Id(projectId, userId)) {
            throw new BusinessException(ErrorCode.PROJECT_ACCESS_DENIED);
        }
    }

    public boolean isProjectMember(Integer projectId, Integer userId) {
        return projectMemberRepository.existsByProject_IdAndUser_Id(projectId, userId);
    }

    public List<Integer> getProjectMemberUserIds(Integer projectId, List<Integer> mentionedUserIds) {
        return projectMemberRepository.findUserIdsInProject(projectId, mentionedUserIds);
    }

    // TODO: 유저테스트 전용 임시 구현 (추후 수정 필요 - validateProjectMemberLimit())
    public void validateProjectMemberLimit(Integer projectId) {
        long memberCount = projectMemberRepository.countByProject_Id(projectId);
        if (memberCount >= TEMP_MAX_PROJECT_MEMBER_COUNT) {
            throw new BusinessException(ErrorCode.FAIL, "프로젝트 최대 인원은 6명입니다.");
        }
    }
}
