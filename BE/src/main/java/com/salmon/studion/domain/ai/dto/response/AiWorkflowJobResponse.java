package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AiWorkflowJobResponse {
    @JsonProperty("job_id")
    private Integer jobId;

    @JsonProperty("project_id")
    private Integer projectId;

    @JsonProperty("dispatch_type")
    private String dispatchType;

    private String status;

    @JsonProperty("queue_name")
    private String queueName;
}
