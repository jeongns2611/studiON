package com.salmon.studion.domain.project.service;

import com.salmon.studion.domain.clip.service.ClipService;
import com.salmon.studion.domain.comment.service.CommentService;
import com.salmon.studion.domain.eq.service.TrackEqService;
import com.salmon.studion.domain.project.dto.response.ProjectSnapshotSaveResponse;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.domain.track.service.TrackService;
import com.salmon.studion.global.common.enums.ProjectSaveTrigger;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProjectSnapshotService {

    private final ProjectService projectService;
    private final TrackService trackService;
    private final ClipService clipService;
    private final CommentService commentService;
    private final TrackEqService trackEqService;
    private final ProjectStatisticsService projectStatisticsService;
    private final Clock clock;

    /*
        DB 작업만 수행
        1. track upsert
        2. clip delete
        3. clip upsert
        4. comment delete
        5. comment upsert
        6. comment mention replace
        7. track delete
        8. eq 동기화
        9. 통계 갱신
     */
    @Transactional
    public ProjectSnapshotSaveResponse save(Integer projectId, ProjectSaveTrigger trigger) {
        projectService.getProjectOrThrow(projectId);

        log.info("[프로젝트 스냅샷 생성 시작] - projectId={} trigger={}", projectId, trigger);

        trackService.upsertTracksFromRedis(projectId);
        clipService.deleteRemovedClipsFromMysql(projectId);
        clipService.upsertClipsFromRedis(projectId);

        commentService.deleteRemovedCommentsFromMysql(projectId);
        commentService.upsertCommentsFromRedis(projectId);
        commentService.replaceCommentMentionsFromRedis(projectId);

        trackService.deleteRemovedTracksFromMysql(projectId);

        List<Track> persistedTracks = trackService.getTracksByProjectId(projectId);
        List<Integer> trackIds = persistedTracks.stream().map(Track::getId).toList();

        trackEqService.synchronizeWithTrackIds(projectId, trackIds);
        projectStatisticsService.refresh(projectId);

        log.info("[프로젝트 스냅샷 생성 완료] - projectId={} trigger={}", projectId, trigger);

        return ProjectSnapshotSaveResponse.of(projectId, trigger, clock.instant());
    }
}
