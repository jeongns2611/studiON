package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.util.Map;
import java.util.List;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AiJobStartRequest {

    @NotNull
    @JsonProperty("job_id")
    private Integer jobId;

    @NotNull
    @JsonProperty("project_id")
    private Integer projectId;

    @JsonProperty("requested_by")
    private Integer requestedBy;

    @NotEmpty
    @JsonProperty("issue_types")
    private List<String> issueTypes;

    @NotBlank
    @JsonProperty("validator_mode")
    private String validatorMode;

    @NotBlank
    @JsonProperty("critic_mode")
    private String criticMode;

    @NotNull
    @JsonProperty("project_snapshot")
    private ProjectSnapshotRequest projectSnapshotRequest;

    public static AiJobStartRequest create(
            Integer jobId,
            AiJobStartApiRequest request,
            Integer requestedBy,
            Map<Integer, String> audioUrlByMetadataId,
            List<ProjectTrackEqRequest> trackEqs,
            ProjectMasterLimiterRequest masterLimiter
    ) {
        ProjectSnapshotRequest sourceSnapshot = request.getProjectSnapshot();
        List<ProjectTrackRequest> tracks = sourceSnapshot.getProjectTrackRequest().stream()
                .map(ProjectTrackRequest::copyOf)
                .toList();
        List<ProjectClipRequest> clips = sourceSnapshot.getProjectClipRequest().stream()
                .map(clip -> {
                    String resolvedAudioUrl = clip.getAudioUrl();
                    if (resolvedAudioUrl == null || resolvedAudioUrl.isBlank()) {
                        resolvedAudioUrl = audioUrlByMetadataId.get(clip.getAudioMetadataId());
                    }
                    return ProjectClipRequest.create(clip, resolvedAudioUrl);
                })
                .toList();

        return new AiJobStartRequest(
                jobId,
                request.getProjectId(),
                requestedBy,
                request.getIssueTypes(),
                request.getValidatorMode(),
                request.getCriticMode(),
                ProjectSnapshotRequest.create(sourceSnapshot, tracks, clips, trackEqs, masterLimiter)
        );
    }
}
