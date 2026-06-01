package com.salmon.studion.domain.limiter.entity;

import com.salmon.studion.global.common.entity.BaseEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Entity
@Table(name = "master_limiter")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class MasterLimiter extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "project_id", nullable = false, unique = true)
    private Integer projectId;

    @Column(name = "is_enabled", nullable = false)
    private Boolean isEnabled;

    @Column(name = "threshold_db", nullable = false)
    private Double thresholdDb;

    @Column(name = "ceiling_dbfs", nullable = false)
    private Double ceilingDbfs;

    @Column(name = "attack_ms", nullable = false)
    private Double attackMs;

    @Column(name = "release_ms", nullable = false)
    private Double releaseMs;

    @Column(name = "input_gain_db", nullable = false)
    private Double inputGainDb;

    @Column(name = "makeup_gain_db", nullable = false)
    private Double makeupGainDb;

    @Column(name = "job_id")
    private Integer jobId;

    @Column(name = "suggestion_action_id")
    private Integer suggestionActionId;

    @Column(name = "applied_suggestion_id")
    private Integer appliedSuggestionId;

    @Column(name = "source_type_code", nullable = false)
    private Integer sourceTypeCode;

    public static MasterLimiter create(Integer projectId) {
        MasterLimiter limiter = new MasterLimiter();
        limiter.projectId = projectId;
        limiter.isEnabled = false;
        limiter.thresholdDb = -6.0;
        limiter.ceilingDbfs = -1.0;
        limiter.attackMs = 3.0;
        limiter.releaseMs = 80.0;
        limiter.inputGainDb = 0.0;
        limiter.makeupGainDb = 0.0;
        limiter.sourceTypeCode = 1;
        return limiter;
    }

    public void update(
            Boolean isEnabled,
            Double thresholdDb,
            Double ceilingDbfs,
            Double attackMs,
            Double releaseMs,
            Double inputGainDb,
            Double makeupGainDb,
            Integer jobId,
            Integer suggestionActionId,
            Integer appliedSuggestionId,
            Integer sourceTypeCode
    ) {
        this.isEnabled = isEnabled;
        this.thresholdDb = thresholdDb;
        this.ceilingDbfs = ceilingDbfs;
        this.attackMs = attackMs;
        this.releaseMs = releaseMs;
        this.inputGainDb = inputGainDb;
        this.makeupGainDb = makeupGainDb;
        this.jobId = jobId;
        this.suggestionActionId = suggestionActionId;
        this.appliedSuggestionId = appliedSuggestionId;
        this.sourceTypeCode = sourceTypeCode;
    }
}
