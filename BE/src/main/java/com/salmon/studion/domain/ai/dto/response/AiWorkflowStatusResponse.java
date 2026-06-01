package com.salmon.studion.domain.ai.dto.response;

import com.fasterxml.jackson.databind.JsonNode;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class AiWorkflowStatusResponse {

    private AiWorkflowJobStatusResponse job;

    private JsonNode projections;
}
