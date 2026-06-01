package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.project.dto.request.ProjectCreateRequest;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.repository.ProjectRepository;
import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.List;

@Service
@RequiredArgsConstructor
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final Clock clock;

    public Project createProject(ProjectCreateRequest projectCreateRequest) {
        Project project = Project.create(
                projectCreateRequest.getName(),
                projectCreateRequest.getRootNote(),
                projectCreateRequest.getProjectMode(),
                projectCreateRequest.getTempo(),
                projectCreateRequest.getTimeSigNumerator(),
                projectCreateRequest.getTimeSigDenominator(),
                clock.instant()
        );

        return projectRepository.save(project);
    }

    public List<Project> getProjectsByIds(List<Integer> projectIds) {
        if (projectIds.isEmpty())
            return List.of();

        return projectRepository.findByIdInOrderByLastUpdateAtDesc(projectIds);
    }

    public Project getProjectOrThrow(Integer projectId) {
        return projectRepository.findById(projectId)
                .orElseThrow(() -> new BusinessException(ErrorCode.PROJECT_NOT_FOUND));
    }

    @Transactional
    public String renameProject(Integer projectId, String name) {
        Project project = getProjectOrThrow(projectId);
        project.rename(name, clock.instant());
        Project savedProject = projectRepository.save(project);
        return savedProject.getName();
    }

    @Transactional
    public Double changeTempo(Integer projectId, Double tempo) {
        if (tempo == null) throw new BusinessException(ErrorCode.INVALID_REQUEST);
        Project project = getProjectOrThrow(projectId);
        project.changeTempo(tempo, clock.instant());
        return projectRepository.save(project).getTempo();
    }

    @Transactional
    public Project changeKey(Integer projectId, RootNote rootNote, ProjectMode mode) {
        if (rootNote == null || mode == null) throw new BusinessException(ErrorCode.INVALID_REQUEST);
        Project project = getProjectOrThrow(projectId);
        project.changeKey(rootNote, mode, clock.instant());
        return projectRepository.save(project);
    }

    @Transactional
    public Project changeTimeSignature(Integer projectId, Integer timeSigNumerator, Integer timeSigDenominator) {
        if (timeSigNumerator == null || timeSigDenominator == null) throw new BusinessException(ErrorCode.INVALID_REQUEST);
        Project project = getProjectOrThrow(projectId);
        project.changeTimeSignature(timeSigNumerator, timeSigDenominator, clock.instant());
        return projectRepository.save(project);
    }
}
