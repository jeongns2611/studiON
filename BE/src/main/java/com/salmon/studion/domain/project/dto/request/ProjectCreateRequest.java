package com.salmon.studion.domain.project.dto.request;

import com.salmon.studion.global.common.enums.ProjectMode;
import com.salmon.studion.global.common.enums.RootNote;
import jakarta.validation.constraints.*;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class ProjectCreateRequest {

    @NotBlank(message = "프로젝트 이름은 필수입니다.")
    @Size(max = 100, message = "프로젝트 이름은 100자 이하여야 합니다.")
    private String name;

    @NotNull(message = "근음은 필수입니다.")
    private RootNote rootNote;

    @NotNull(message = "조성은 필수입니다.")
    private ProjectMode projectMode;

    @NotNull(message = "템포는 필수입니다.")
    @DecimalMin(value = "1.0", message = "템포는 1 이상이어야 합니다.")
    @DecimalMax(value = "400.0", message = "템포는 400 이하여야 합니다.")
    private Double tempo;

    @NotNull(message = "박자 분자는 필수입니다.")
    @Min(value = 1, message = "박자 분자는 1 이상이어야 합니다.")
    private Integer timeSigNumerator;

    @NotNull(message = "박자 분모는 필수입니다.")
    @Min(value = 1, message = "박자 분모는 1 이상이어야 합니다.")
    private Integer timeSigDenominator;

}
