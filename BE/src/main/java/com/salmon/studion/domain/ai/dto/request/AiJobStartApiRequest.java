package com.salmon.studion.domain.ai.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;

@Getter
@NoArgsConstructor
public class AiJobStartApiRequest {

    @NotNull
    @JsonProperty("project_id")
    private Integer projectId;

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
    private ProjectSnapshotRequest projectSnapshot;
}
