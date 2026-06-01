package com.salmon.studion.domain.project.dto.response;

import com.salmon.studion.global.common.enums.ProjectSaveTrigger;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.Instant;

@Getter
@AllArgsConstructor
public class ProjectSnapshotSaveResponse {

    private Integer projectId;
    private String trigger;
    private Instant saveAt;

    public static ProjectSnapshotSaveResponse of(Integer projectId, ProjectSaveTrigger trigger, Instant saveAt) {
        return new ProjectSnapshotSaveResponse(projectId, trigger.name(), saveAt);
    }
}
