package com.salmon.studion.domain.project.facade;

import com.salmon.studion.domain.audio.entity.AudioMetadata;
import com.salmon.studion.domain.audio.service.AudioService;
import com.salmon.studion.domain.audio.service.AudioUploadLimitService;
import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.service.UserService;
import com.salmon.studion.domain.clip.entity.Clip;
import com.salmon.studion.domain.clip.service.ClipService;
import com.salmon.studion.domain.comment.dto.response.CommentsGetResponse;
import com.salmon.studion.domain.comment.facade.CommentFacade;
import com.salmon.studion.domain.limiter.service.MasterLimiterService;
import com.salmon.studion.domain.project.dto.request.ProjectCreateRequest;
import com.salmon.studion.domain.project.dto.response.ProjectCreateResponse;
import com.salmon.studion.domain.project.dto.response.ProjectDetailResponse;
import com.salmon.studion.domain.project.dto.response.ProjectListResponse;
import com.salmon.studion.domain.project.dto.response.ProjectSnapshotSaveResponse;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.domain.project.entity.ProjectMember;
import com.salmon.studion.domain.track.service.MasterTrackService;
import com.salmon.studion.domain.project.service.ProjectMemberService;
import com.salmon.studion.domain.project.service.ProjectSaveService;
import com.salmon.studion.domain.project.service.ProjectService;
import com.salmon.studion.domain.track.entity.MasterTrack;
import com.salmon.studion.domain.track.entity.Track;
import com.salmon.studion.domain.track.dto.response.TrackAddResponse;
import com.salmon.studion.domain.track.service.TrackService;
import com.salmon.studion.global.infrastructure.cdn.CdnUrlService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Component
@RequiredArgsConstructor
public class ProjectFacade {

    private final ProjectService projectService;
    private final ProjectMemberService projectMemberService;
    private final ProjectSaveService projectSaveService;
    private final MasterTrackService masterTrackService;
    private final MasterLimiterService masterLimiterService;
    private final UserService userService;
    private final TrackService trackService;
    private final ClipService clipService;
    private final CommentFacade commentFacade;
    private final AudioService audioService;
    private final AudioUploadLimitService audioUploadLimitService;
    private final CdnUrlService cdnUrlService;

    @Transactional(readOnly = true)
    public ProjectDetailResponse getProjectDetail(Integer projectId, Integer userId) {
        Project project = projectService.getProjectOrThrow(projectId);

        projectMemberService.validateProjectMember(projectId, userId);

        MasterTrack masterTrack = masterTrackService.getMasterTrackOrThrow(projectId);

        boolean useWorkingSet = hasProjectWorkingSet(projectId);

        List<Track> tracks = useWorkingSet
                ? trackService.getTracksForProjectDetail(projectId)
                : trackService.getTracksByProjectId(projectId);

        List<Clip> clips = List.of();
        if (!tracks.isEmpty()) {
            clips = useWorkingSet
                    ? clipService.getClipsForProjectDetail(projectId, tracks)
                    : clipService.getClipsWithAudioMetadataByTrackIds(
                    tracks.stream().map(Track::getId).toList()
            );
        }

        List<CommentsGetResponse.CommentDto> comments =
                commentFacade.getCommentsForProjectDetail(projectId, userId);

        User user = userService.getUserByUserId(userId);
        long currentTotalSizeBytes = audioService.sumSizeBytesByCreatedBy(userId);
        long maxTotalSizeBytes = audioUploadLimitService.getLimit(user.getRole()).maxTotalSizeBytes();

        List<ProjectMember> members = projectMemberService.getMembersWithUserByProjectIds(List.of(projectId));

        return toProjectDetailResponse(
                project,
                masterTrack,
                tracks,
                clips,
                comments,
                currentTotalSizeBytes,
                maxTotalSizeBytes,
                members
        );
    }

    @Transactional(readOnly = true)
    public ProjectListResponse getProjectList(Integer userId) {
        /*
            1. userId로 내가 참여한 projectId 목록 조회
            2. projectId 목록으로 프로젝트 정보 한 번에 조회
            3. projectId 목록으로 각 프로젝트의 멤버 + 유저 프로필 한 번에 조회
            4. projectId 기준으로 묶어서 Response 생성
         */
        List<Integer> projectIds = projectMemberService.getProjectIdsByUserId(userId);
        List<Project> projects = projectService.getProjectsByIds(projectIds);
        List<ProjectMember> members = projectMemberService.getMembersWithUserByProjectIds(projectIds);

        // projectId 기준으로 userId 묶기
        Map<Integer, List<ProjectMember>> membersByProjectId = members.stream()
                .collect(Collectors.groupingBy(pm -> pm.getProject().getId()));

        // 프로젝트 목록을 dto로 변환
        List<ProjectListResponse.ProjectSummary> projectSummaries = projects.stream()
                .map(project -> {
                    List<ProjectListResponse.MemberSummary> memberSummaries =
                            membersByProjectId.getOrDefault(project.getId(), List.of())
                                    .stream()
                                    .map(pm -> new ProjectListResponse.MemberSummary(
                                            pm.getUser().getId(),
                                            pm.getUser().getProfileImgUrl()
                                    ))
                                    .toList();

                    return new ProjectListResponse.ProjectSummary(
                            project.getId(),
                            project.getName(),
                            project.getTotalBarCount(),
                            project.getTotalPlayTimeMs(),
                            project.getTotalAudioSizeByte(),
                            project.getLastUpdateAt(),
                            memberSummaries
                    );
                })
                .toList();

        User user = userService.getUserByUserId(userId);
        long currentTotalSizeBytes = audioService.sumSizeBytesByCreatedBy(userId);
        long maxTotalSizeBytes = audioUploadLimitService.getLimit(user.getRole()).maxTotalSizeBytes();

        return new ProjectListResponse(projectSummaries, currentTotalSizeBytes, maxTotalSizeBytes);
    }

    @Transactional
    public ProjectCreateResponse createProject(ProjectCreateRequest projectCreateRequest, Integer userId) {
        Project project = projectService.createProject(projectCreateRequest);
        MasterTrack masterTrack = masterTrackService.createMasterTrack(project);
        masterLimiterService.createIfAbsent(project.getId());

        User user = userService.getUserByUserId(userId);
        projectMemberService.createProjectMember(project, user);

        TrackAddResponse defaultTrack = trackService.addDefaultTrack(project.getId(), userId);

        return ProjectCreateResponse.builder()
                .project(new ProjectCreateResponse.ProjectInfo(
                        project.getId(),
                        project.getName(),
                        project.getRootNote(),
                        project.getMode(),
                        project.getTempo(),
                        project.getTimeSigNumerator(),
                        project.getTimeSigDenominator(),
                        project.getTotalBarCount(),
                        project.getTotalPlayTimeMs()
                ))
                .masterTrack(new ProjectCreateResponse.MasterTrackInfo(
                        masterTrack.getId(),
                        masterTrack.getIsSoloed(),
                        masterTrack.getIsMuted(),
                        masterTrack.getVolume(),
                        masterTrack.getPan()
                ))
                .defaultTrack(new ProjectCreateResponse.TrackInfo(
                        defaultTrack.getTrackId(),
                        defaultTrack.getName(),
                        defaultTrack.getType(),
                        defaultTrack.getPreTrackId(),
                        defaultTrack.getPostTrackId(),
                        defaultTrack.getIsMuted(),
                        defaultTrack.getIsSoloed(),
                        defaultTrack.getVolume(),
                        defaultTrack.getPan()
                ))
                .build();
    }

    public ProjectSnapshotSaveResponse saveProjectSnapshot(Integer projectId, Integer userId) {
        projectMemberService.validateProjectMember(projectId, userId);
        return projectSaveService.saveManually(projectId);
    }

    private boolean hasProjectWorkingSet(Integer projectId) {
        return trackService.hasTrackWorkingSet(projectId)
                || clipService.hasClipWorkingSet(projectId)
                || commentFacade.hasCommentWorkingSet(projectId);
    }

    private ProjectDetailResponse toProjectDetailResponse(
            Project project,
            MasterTrack masterTrack,
            List<Track> tracks,
            List<Clip> clips,
            List<CommentsGetResponse.CommentDto> comments,
            Long currentTotalSizeBytes,
            Long maxTotalSizeBytes,
            List<ProjectMember> members
    ) {
        Map<Integer, List<Clip>> clipsByTrackId = clips.stream()
                .collect(Collectors.groupingBy(clip -> clip.getTrack().getId()));

        ProjectDetailResponse.MasterTrackResponse masterTrackResponse = toMasterTrackResponse(masterTrack);

        List<ProjectDetailResponse.TrackResponse> trackResponses = tracks.stream()
                .map(track -> toTrackResponse(track, clipsByTrackId.getOrDefault(track.getId(), List.of())))
                .toList();

        List<ProjectDetailResponse.MemberResponse> memberResponses = members.stream()
                .map(pm -> new ProjectDetailResponse.MemberResponse(
                        pm.getUser().getId(),
                        pm.getUser().getNickname(),
                        pm.getUser().getProfileImgUrl()
                ))
                .toList();

        return ProjectDetailResponse.of(
                project,
                masterTrackResponse,
                trackResponses,
                comments,
                currentTotalSizeBytes,
                maxTotalSizeBytes,
                memberResponses
        );
    }

    private ProjectDetailResponse.MasterTrackResponse toMasterTrackResponse(MasterTrack masterTrack) {
        return new ProjectDetailResponse.MasterTrackResponse(
                masterTrack.getId(),
                masterTrack.getIsSoloed(),
                masterTrack.getIsMuted(),
                masterTrack.getVolume(),
                masterTrack.getPan()
        );
    }

    private ProjectDetailResponse.TrackResponse toTrackResponse(Track track, List<Clip> clips) {
        List<ProjectDetailResponse.ClipResponse> clipResponses = clips.stream()
                .map(this::toClipResponse)
                .toList();
        return new ProjectDetailResponse.TrackResponse(
                track.getId(),
                track.getName(),
                track.getTrackType(),
                track.getPreTrackId(),
                track.getPostTrackId(),
                track.getIsMuted(),
                track.getIsSoloed(),
                track.getVolume(),
                track.getPan(),
                clipResponses
        );
    }

    private ProjectDetailResponse.ClipResponse toClipResponse(Clip clip) {
        AudioMetadata audioMetadata = clip.getAudioMetadata();

        return new ProjectDetailResponse.ClipResponse(
                clip.getId(),
                clip.getStart(),
                clip.getDuration(),
                clip.getAudioStartMs(),
                clip.getAudioDurationMs(),
                clip.getColor(),
                toAudioResponse(audioMetadata)
        );
    }

    private ProjectDetailResponse.AudioResponse toAudioResponse(AudioMetadata audioMetadata) {
        return new ProjectDetailResponse.AudioResponse(
                audioMetadata.getId(),
                cdnUrlService.createAudioUrl(audioMetadata.getObjectKey()),
                audioMetadata.getOriginalName(),
                audioMetadata.getDurationMs()
        );
    }

}
