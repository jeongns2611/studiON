package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.clip.service.ClipService;
import com.salmon.studion.domain.comment.service.CommentService;
import com.salmon.studion.domain.project.dto.response.ProjectSnapshotSaveResponse;
import com.salmon.studion.domain.track.service.TrackService;
import com.salmon.studion.global.common.enums.ProjectSaveTrigger;
import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Optional;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProjectSaveService {

    private final ProjectSnapshotService projectSnapshotService;
    private final ProjectDirtyStateService projectDirtyStateService;
    private final TrackService trackService;
    private final ClipService clipService;
    private final CommentService commentService;

    private static final int MAX_AUTOSAVE_FAIL_COUNT = 5;

    public ProjectSnapshotSaveResponse saveManually(Integer projectId) {
        if (!projectDirtyStateService.acquireSavingLock(projectId)) {
            throw new BusinessException(ErrorCode.PROJECT_SAVE_IN_PROGRESS);
        }

        try {
            ProjectSnapshotSaveResponse response = projectSnapshotService.save(projectId, ProjectSaveTrigger.MANUAL);

            trackService.clearDeletedTrackKeys(projectId);
            clipService.clearDeletedClipKeys(projectId);
            commentService.clearDeletedCommentKeys(projectId);

            projectDirtyStateService.markSaveSuccess(projectId);
            return response;
        } catch (RuntimeException e) {
            projectDirtyStateService.incrementFailCount(projectId);
            log.error("[프로젝트 수동 저장 실패] | projectId={}", projectId, e);
            throw e;
        } finally {
            projectDirtyStateService.releaseSavingLock(projectId);
        }
    }

    public Optional<ProjectSnapshotSaveResponse> saveIfDirty(Integer projectId, ProjectSaveTrigger trigger) {
        if (!projectDirtyStateService.isDirty(projectId)) {
            return Optional.empty();
        }

        long failCount = projectDirtyStateService.getFailCount(projectId);
        if (failCount >= MAX_AUTOSAVE_FAIL_COUNT) {
            log.warn("[프로젝트 자동저장 중단] 최대 실패 횟수 초과 | projectId={} failCount={}", projectId, failCount);
            return Optional.empty();
        }

        if (!projectDirtyStateService.acquireSavingLock(projectId)) {
            log.debug("[프로젝트 자동저장 skip] 저장 진행 중 | projectId={}", projectId);
            return Optional.empty();
        }

        try {
            ProjectSnapshotSaveResponse response = projectSnapshotService.save(projectId, trigger);

            trackService.clearDeletedTrackKeys(projectId);
            clipService.clearDeletedClipKeys(projectId);
            commentService.clearDeletedCommentKeys(projectId);

            projectDirtyStateService.markSaveSuccess(projectId);
            return Optional.of(response);
        } catch (RuntimeException e) {
            long nextFailCount = projectDirtyStateService.incrementFailCount(projectId);
            log.error("[프로젝트 자동저장 실패] projectId={} trigger= {} failCount={}", projectId, trigger, nextFailCount, e);
            return Optional.empty();
        } finally {
            projectDirtyStateService.releaseSavingLock(projectId);
        }
    }
}
