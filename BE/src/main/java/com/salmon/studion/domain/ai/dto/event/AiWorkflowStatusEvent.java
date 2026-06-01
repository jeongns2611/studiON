package com.salmon.studion.domain.ai.dto.event;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class AiWorkflowStatusEvent {

    private String type;
    private Integer jobId;
    private Integer projectId;
    private String status;
    private String phase;
    private Integer progress;
    private JsonNode projections;
    private String errorCode;
    private String errorMessage;
}
