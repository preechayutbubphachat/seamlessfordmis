<?php

namespace Tests\Unit;

use App\Services\Review\TargetGroupReviewService;
use Tests\TestCase;

final class TargetGroupReviewReasonTest extends TestCase
{
    public function test_authoritative_and_foundation_reason_sets_are_exact(): void
    {
        $service = app(TargetGroupReviewService::class);

        $this->assertSame([
            'MISSING_CID',
            'INVALID_CID_FORMAT',
            'INVALID_CID_CHECK_DIGIT',
            'DUPLICATE_WITHIN_FILE',
            'DUPLICATE_WITHIN_BATCH',
            'DUPLICATE_ACROSS_FILES',
            'NAME_CONFLICT',
            'BIRTH_DATE_CONFLICT',
            'PROGRAM_SCOPE_CONFLICT',
            'HOSPITAL_SCOPE_CONFLICT',
            'AMBIGUOUS_HISTORY',
            'CORRECTED_FILE_VERSION',
            'SOURCE_EVIDENCE_CONFLICT',
        ], $service->authoritativeReasonCodes());

        $this->assertSame([
            'MISSING_CID',
            'INVALID_CID_FORMAT',
            'INVALID_CID_CHECK_DIGIT',
            'DUPLICATE_WITHIN_FILE',
            'DUPLICATE_WITHIN_BATCH',
            'NAME_CONFLICT',
            'BIRTH_DATE_CONFLICT',
            'AMBIGUOUS_HISTORY',
            'SOURCE_EVIDENCE_CONFLICT',
        ], $service->foundationReasonCodes());

        $this->assertCount(13, $service->authoritativeReasonCodes());
        $this->assertCount(9, $service->foundationReasonCodes());
        $this->assertFalse($service->isFoundationReason('DUPLICATE_ACROSS_FILES'));
    }

    public function test_cid_reason_classification_is_fail_closed(): void
    {
        $service = app(TargetGroupReviewService::class);

        $this->assertSame('MISSING_CID', $service->reviewReasonForCid(null));
        $this->assertSame('MISSING_CID', $service->reviewReasonForCid('   '));
        $this->assertSame('INVALID_CID_FORMAT', $service->reviewReasonForCid('123456789012'));
        $this->assertSame('INVALID_CID_FORMAT', $service->reviewReasonForCid('123456789012X'));
        $this->assertSame('INVALID_CID_CHECK_DIGIT', $service->reviewReasonForCid('1234567890120'));
        $this->assertNull($service->reviewReasonForCid('1234567890121'));
    }
}
