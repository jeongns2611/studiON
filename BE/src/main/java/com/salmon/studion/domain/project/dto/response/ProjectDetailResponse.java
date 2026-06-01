package com.salmon.studion.domain.project.dto.response;

import com.salmon.studion.domain.comment.dto.response.CommentsGetResponse;
import com.salmon.studion.domain.project.entity.Project;
import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import com.salmon.studion.global.common.enums.TrackType;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@AllArgsConstructor
@NoArgsConstructor
public class ProjectDetailResponse {

    private Integer projectId;
    private String  name;
    private RootNote rootNote;
    private ProjectMode mode;
    private Double tempo;
    private Integer timeSigNumerator;
    private Integer timeSigDenominator;
    private Integer totalBarCount;
    private Integer totalPlayTimeMs;
    private MasterTrackResponse masterTrack;
    private List<TrackResponse> tracks;
    private List<CommentsGetResponse.CommentDto> comments;
    private Long currentTotalSizeBytes;
    private Long maxTotalSizeBytes;
    private List<MemberResponse> members;

    public record MasterTrackResponse (
            Integer masterTrackId,
            Boolean isSoloed,
            Boolean isMuted,
            Double volume,
            Integer pan
    ) {}

    public record TrackResponse (
            Integer trackId,
            String name,
            TrackType type,
            Integer preTrackId,
            Integer postTrackId,
            Boolean isMuted,
            Boolean isSoloed,
            Double volume,
            Integer pan,
            List<ClipResponse> clips
    ) {}

    public record ClipResponse (
            Integer clipId,
            Double start,
            Double duration,
            Integer audioStartMs,
            Integer audioDurationMs,
            String color,
            AudioResponse audio
    ) {}

    public record AudioResponse (
            Integer audioMetadataId,
            String cdnUrl,
            String originalName,
            Integer durationMs
    ) {}

    public record MemberResponse (
            Integer userId,
            String nickname,
            String profileImageUrl
    ) {}

    public static ProjectDetailResponse of(
            Project project,
            MasterTrackResponse masterTrack,
            List<TrackResponse> tracks,
            List<CommentsGetResponse.CommentDto> comments,
            Long currentTotalSizeBytes,
            Long maxTotalSizeBytes,
            List<MemberResponse> members
    ) {
        return new ProjectDetailResponse(
                project.getId(),
                project.getName(),
                project.getRootNote(),
                project.getMode(),
                project.getTempo(),
                project.getTimeSigNumerator(),
                project.getTimeSigDenominator(),
                project.getTotalBarCount(),
                project.getTotalPlayTimeMs(),
                masterTrack,
                tracks,
                comments,
                currentTotalSizeBytes,
                maxTotalSizeBytes,
                members
        );
    }
}
